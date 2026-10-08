import { getPool } from "./db";

export type Period = "day" | "week" | "month";

export function windowDays(period: Period): number {
  if (period === "day") return 1;
  if (period === "week") return 7;
  return 30;
}

/** Formats a Date as YYYY-MM-DD in a given IANA timezone, without any date library. */
function localDateString(timezone: string): string {
  try {
    return new Intl.DateTimeFormat("en-CA", { timeZone: timezone }).format(new Date());
  } catch {
    return new Intl.DateTimeFormat("en-CA", { timeZone: "UTC" }).format(new Date());
  }
}

function toISODate(date: Date): string {
  return date.toISOString().slice(0, 10);
}

export function resolveDateRange(
  period: Period,
  timezone: string,
  anchorDate?: string
): { start: string; end: string } {
  const end = anchorDate ?? localDateString(timezone);
  const days = windowDays(period);
  const endDate = new Date(`${end}T00:00:00Z`);
  const startDate = new Date(endDate);
  startDate.setUTCDate(startDate.getUTCDate() - (days - 1));
  return { start: toISODate(startDate), end };
}

function toDateOnly(value: unknown): string {
  // node-postgres parses `date` columns into JS Date objects at UTC midnight.
  return value instanceof Date ? value.toISOString().slice(0, 10) : String(value);
}

export interface DashboardUser {
  id: number;
  phoneHash: string;
  name: string | null;
  timezone: string;
  unitSystem: string;
  goalType: string | null;
  age: number | null;
  sex: string | null;
  heightCm: number | null;
  weightKg: number | null;
  activityLevel: string | null;
}

export async function getUserByPhoneHash(phoneHash: string): Promise<DashboardUser | null> {
  const { rows } = await getPool().query(
    `SELECT id, phone_hash, name, timezone, unit_system, goal_type,
            age, sex, height_cm, weight_kg, activity_level
     FROM users WHERE phone_hash = $1`,
    [phoneHash]
  );
  if (rows.length === 0) return null;
  const row = rows[0];
  return {
    id: row.id,
    phoneHash: row.phone_hash,
    name: row.name,
    timezone: row.timezone ?? "UTC",
    unitSystem: row.unit_system,
    goalType: row.goal_type,
    age: row.age,
    sex: row.sex,
    heightCm: row.height_cm !== null ? Number(row.height_cm) : null,
    weightKg: row.weight_kg !== null ? Number(row.weight_kg) : null,
    activityLevel: row.activity_level,
  };
}

// Mirrors ai_fitness_coach_rag/db/scoring.py ACTIVITY_MULTIPLIERS.
const ACTIVITY_MULTIPLIERS: Record<string, number> = {
  sedentary: 1.2,
  light: 1.375,
  moderate: 1.55,
  active: 1.725,
  very_active: 1.9,
};

// Mirrors config.yaml `scoring` defaults (steps_target, water_target_ml, protein_target_g_per_kg).
const STEPS_TARGET = 10000;
const WATER_TARGET_ML = 2500;
const PROTEIN_TARGET_G_PER_KG = 1.8;

export interface DailyTargets {
  calorieTarget: number | null;
  proteinTarget: number | null;
  waterTarget: number;
  stepsTarget: number;
}

/** Mirrors ai_fitness_coach_rag/db/score_service.py::daily_targets (Mifflin-St Jeor BMR -> TDEE). */
export function calculateDailyTargets(user: DashboardUser): DailyTargets {
  const { weightKg, heightCm, age, sex, activityLevel } = user;
  const multiplier = activityLevel ? ACTIVITY_MULTIPLIERS[activityLevel] : undefined;
  let calorieTarget: number | null = null;
  let proteinTarget: number | null = null;

  if (weightKg && heightCm && age && sex && multiplier) {
    const base = 10 * weightKg + 6.25 * heightCm - 5 * age;
    const bmr = sex === "male" ? base + 5 : base - 161;
    calorieTarget = bmr * multiplier;
    proteinTarget = weightKg * PROTEIN_TARGET_G_PER_KG;
  }

  return { calorieTarget, proteinTarget, waterTarget: WATER_TARGET_ML, stepsTarget: STEPS_TARGET };
}

export interface DailyLogRow {
  id: number;
  logType: "food" | "workout" | "metric" | "water";
  logDate: string;
  description: string | null;
  quantity: string | null;
  calories: number | null;
  proteinG: number | null;
  carbsG: number | null;
  fatG: number | null;
  durationMinutes: number | null;
  caloriesBurned: number | null;
  waterMl: number | null;
  metricName: string | null;
  metricValue: number | null;
  source: string;
}

export async function getLogs(
  userId: number,
  period: Period,
  timezone: string,
  logType?: string,
  anchorDate?: string
): Promise<DailyLogRow[]> {
  const { start, end } = resolveDateRange(period, timezone, anchorDate);
  const params: unknown[] = [userId, start, end];
  let typeFilter = "";
  if (logType && logType !== "all") {
    params.push(logType);
    // log_type is stored as the enum NAME (e.g. 'FOOD'), not the lowercase value.
    typeFilter = `AND UPPER(log_type) = UPPER($${params.length})`;
  }

  const { rows } = await getPool().query(
    `SELECT id, log_type, log_date, description, quantity, calories, protein_g, carbs_g,
            fat_g, duration_minutes, calories_burned, water_ml, metric_name, metric_value, source
     FROM daily_logs
     WHERE user_id = $1 AND log_date BETWEEN $2 AND $3 ${typeFilter}
     ORDER BY log_date DESC, id DESC`,
    params
  );

  return rows.map((row) => ({
    id: row.id,
    logType: String(row.log_type).toLowerCase() as DailyLogRow["logType"],
    logDate: toDateOnly(row.log_date),
    description: row.description,
    quantity: row.quantity,
    calories: row.calories,
    proteinG: row.protein_g,
    carbsG: row.carbs_g,
    fatG: row.fat_g,
    durationMinutes: row.duration_minutes,
    caloriesBurned: row.calories_burned,
    waterMl: row.water_ml,
    metricName: row.metric_name,
    metricValue: row.metric_value,
    source: row.source,
  }));
}

/** Buckets logs (already sorted log_date DESC) by date, preserving that order within each bucket. */
export function groupLogsByDate(logs: DailyLogRow[]): Map<string, DailyLogRow[]> {
  const map = new Map<string, DailyLogRow[]>();
  for (const log of logs) {
    const bucket = map.get(log.logDate);
    if (bucket) bucket.push(log);
    else map.set(log.logDate, [log]);
  }
  return map;
}

export interface ScoreRow {
  id: number;
  scoreDate: string;
  overallScore: number;
  calorieScore: number;
  proteinScore: number;
  activityScore: number;
  waterScore: number;
  consistencyScore: number;
}

export async function getScores(
  userId: number,
  period: Period,
  timezone: string,
  anchorDate?: string
): Promise<ScoreRow[]> {
  const { start, end } = resolveDateRange(period, timezone, anchorDate);
  const { rows } = await getPool().query(
    `SELECT id, score_date, overall_score, calorie_score, protein_score, activity_score,
            water_score, consistency_score
     FROM scores
     WHERE user_id = $1 AND score_date BETWEEN $2 AND $3
     ORDER BY score_date ASC`,
    [userId, start, end]
  );

  return rows.map((row) => ({
    id: row.id,
    scoreDate: toDateOnly(row.score_date),
    overallScore: Number(row.overall_score),
    calorieScore: Number(row.calorie_score),
    proteinScore: Number(row.protein_score),
    activityScore: Number(row.activity_score),
    waterScore: Number(row.water_score),
    consistencyScore: Number(row.consistency_score),
  }));
}

export interface DailyCardData {
  date: string;
  calories: number;
  proteinG: number;
  waterMl: number;
  workoutCount: number;
  workoutMinutes: number;
  steps: number;
  overallScore: number | null;
}

export async function getDailyCards(
  userId: number,
  period: Period,
  timezone: string,
  anchorDate?: string
): Promise<DailyCardData[]> {
  const { start, end } = resolveDateRange(period, timezone, anchorDate);
  const pool = getPool();

  const [logRows, deviceRows, scoreRows] = await Promise.all([
    pool.query(
      `SELECT log_date,
              COALESCE(SUM(calories) FILTER (WHERE UPPER(log_type) = 'FOOD'), 0) AS calories,
              COALESCE(SUM(protein_g) FILTER (WHERE UPPER(log_type) = 'FOOD'), 0) AS protein_g,
              COALESCE(SUM(water_ml) FILTER (WHERE UPPER(log_type) = 'WATER'), 0) AS water_ml,
              COUNT(*) FILTER (WHERE UPPER(log_type) = 'WORKOUT') AS workout_count,
              COALESCE(SUM(duration_minutes) FILTER (WHERE UPPER(log_type) = 'WORKOUT'), 0) AS workout_minutes,
              COALESCE(MAX(metric_value) FILTER (WHERE UPPER(log_type) = 'METRIC' AND metric_name = 'steps'), 0) AS logged_steps
       FROM daily_logs
       WHERE user_id = $1 AND log_date BETWEEN $2 AND $3
       GROUP BY log_date`,
      [userId, start, end]
    ),
    pool.query(
      `SELECT metric_date, COALESCE(MAX(steps), 0) AS steps
       FROM device_metrics
       WHERE user_id = $1 AND metric_date BETWEEN $2 AND $3
       GROUP BY metric_date`,
      [userId, start, end]
    ),
    pool.query(
      `SELECT score_date, overall_score
       FROM scores
       WHERE user_id = $1 AND score_date BETWEEN $2 AND $3`,
      [userId, start, end]
    ),
  ]);

  const deviceStepsByDate = new Map<string, number>();
  for (const row of deviceRows.rows) {
    deviceStepsByDate.set(toDateOnly(row.metric_date), Number(row.steps));
  }
  const scoreByDate = new Map<string, number>();
  for (const row of scoreRows.rows) {
    scoreByDate.set(toDateOnly(row.score_date), Number(row.overall_score));
  }

  const cards: DailyCardData[] = logRows.rows.map((row) => {
    const date = toDateOnly(row.log_date);
    return {
      date,
      calories: Number(row.calories),
      proteinG: Number(row.protein_g),
      waterMl: Number(row.water_ml),
      workoutCount: Number(row.workout_count),
      workoutMinutes: Number(row.workout_minutes),
      // Device-synced steps and user-logged steps can both exist for a date; take the larger.
      steps: Math.max(Number(row.logged_steps), deviceStepsByDate.get(date) ?? 0),
      overallScore: scoreByDate.get(date) ?? null,
    };
  });

  const seenDates = new Set(cards.map((card) => card.date));
  for (const row of deviceRows.rows) {
    const date = toDateOnly(row.metric_date);
    if (seenDates.has(date)) continue;
    cards.push({
      date,
      calories: 0,
      proteinG: 0,
      waterMl: 0,
      workoutCount: 0,
      workoutMinutes: 0,
      steps: Number(row.steps),
      overallScore: scoreByDate.get(date) ?? null,
    });
    seenDates.add(date);
  }

  return cards.sort((a, b) => (a.date < b.date ? 1 : -1));
}

export interface SummaryData {
  totalCalories: number;
  totalProteinG: number;
  totalCarbsG: number;
  totalFatG: number;
  totalWaterMl: number;
  workoutCount: number;
  workoutMinutes: number;
  avgOverallScore: number | null;
  daysLogged: number;
}

export async function getSummary(
  userId: number,
  period: Period,
  timezone: string,
  anchorDate?: string
): Promise<SummaryData> {
  const { start, end } = resolveDateRange(period, timezone, anchorDate);
  const pool = getPool();

  const [logTotals, scoreAvg] = await Promise.all([
    pool.query(
      `SELECT
         COALESCE(SUM(calories) FILTER (WHERE UPPER(log_type) = 'FOOD'), 0) AS total_calories,
         COALESCE(SUM(protein_g) FILTER (WHERE UPPER(log_type) = 'FOOD'), 0) AS total_protein_g,
         COALESCE(SUM(carbs_g) FILTER (WHERE UPPER(log_type) = 'FOOD'), 0) AS total_carbs_g,
         COALESCE(SUM(fat_g) FILTER (WHERE UPPER(log_type) = 'FOOD'), 0) AS total_fat_g,
         COALESCE(SUM(water_ml) FILTER (WHERE UPPER(log_type) = 'WATER'), 0) AS total_water_ml,
         COUNT(*) FILTER (WHERE UPPER(log_type) = 'WORKOUT') AS workout_count,
         COALESCE(SUM(duration_minutes) FILTER (WHERE UPPER(log_type) = 'WORKOUT'), 0) AS workout_minutes,
         COUNT(DISTINCT log_date) AS days_logged
       FROM daily_logs
       WHERE user_id = $1 AND log_date BETWEEN $2 AND $3`,
      [userId, start, end]
    ),
    pool.query(
      `SELECT AVG(overall_score) AS avg_overall_score
       FROM scores WHERE user_id = $1 AND score_date BETWEEN $2 AND $3`,
      [userId, start, end]
    ),
  ]);

  const row = logTotals.rows[0];
  const avg = scoreAvg.rows[0].avg_overall_score;
  return {
    totalCalories: Number(row.total_calories),
    totalProteinG: Number(row.total_protein_g),
    totalCarbsG: Number(row.total_carbs_g),
    totalFatG: Number(row.total_fat_g),
    totalWaterMl: Number(row.total_water_ml),
    workoutCount: Number(row.workout_count),
    workoutMinutes: Number(row.workout_minutes),
    daysLogged: Number(row.days_logged),
    avgOverallScore: avg !== null ? Number(avg) : null,
  };
}

export interface PlanRow {
  id: number;
  planType: "meal" | "workout";
  content: string;
  createdAt: string;
}

export async function getPlans(
  userId: number,
  planType?: "meal" | "workout"
): Promise<PlanRow[]> {
  const params: unknown[] = [userId];
  let typeFilter = "";
  if (planType) {
    params.push(planType);
    typeFilter = "AND plan_type = $2";
  }

  const { rows } = await getPool().query(
    `SELECT id, plan_type, content, created_at
     FROM plans
     WHERE user_id = $1 ${typeFilter}
     ORDER BY created_at DESC
     LIMIT 10`,
    params
  );

  return rows.map((row) => ({
    id: row.id,
    planType: row.plan_type,
    content: row.content,
    createdAt: row.created_at instanceof Date ? row.created_at.toISOString() : String(row.created_at),
  }));
}
