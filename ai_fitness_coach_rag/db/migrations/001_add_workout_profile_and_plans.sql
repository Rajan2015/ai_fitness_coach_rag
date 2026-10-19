-- Step 1: workout profile and approved workout-plan persistence.
-- Apply this migration once to an existing PostgreSQL database.

CREATE TABLE IF NOT EXISTS workout_profiles (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL UNIQUE REFERENCES users (id),
    training_experience VARCHAR(32) NOT NULL,
    CHECK (training_experience IN ('beginner', 'intermediate', 'advanced')),
    equipment JSONB NOT NULL DEFAULT '[]'::jsonb,
    workout_days_per_week INTEGER NOT NULL
        CHECK (workout_days_per_week BETWEEN 1 AND 7),
    session_duration_minutes INTEGER NOT NULL
        CHECK (session_duration_minutes > 0),
    preferences JSONB NOT NULL DEFAULT '[]'::jsonb,
    injuries_or_limitations TEXT NULL,
    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL
        DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_workout_profiles_user_id
    ON workout_profiles (user_id);

CREATE TABLE IF NOT EXISTS workout_plans (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users (id),
    status VARCHAR(16) NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'active', 'archived')),
    title VARCHAR(200) NOT NULL,
    goal_type VARCHAR(16) NOT NULL
        CHECK (goal_type IN ('lose', 'gain', 'maintain')),
    plan_json JSONB NOT NULL,
    profile_snapshot_json JSONB NOT NULL,
    approved_at TIMESTAMP WITHOUT TIME ZONE NULL,
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL
        DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_workout_plans_user_id
    ON workout_plans (user_id);

CREATE INDEX IF NOT EXISTS ix_workout_plans_user_status
    ON workout_plans (user_id, status);
