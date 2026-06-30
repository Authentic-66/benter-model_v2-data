-- Benter Model v2 — Phase 3A schema
-- SQLite. Normalized for cross-track expansion. NULLs mean "unknown" — never imputed.
-- Designed for ~100k+ races. Indexed on the queries feature engineering will hit hardest:
-- track+date, horse, trainer, jockey, finish.

PRAGMA foreign_keys = ON;

-- =====================================================================
-- Reference dimensions: tracks, people, bloodlines.
-- All lookup tables use a normalized_name field (lowercased, punctuation-
-- stripped) so that "Ortiz,Jr.,Irad" and "Ortiz Jr Irad" merge to one row.
-- =====================================================================

CREATE TABLE IF NOT EXISTS tracks (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    code            TEXT NOT NULL UNIQUE,           -- 'GP', 'CT', 'EVD' ...
    name            TEXT,                            -- 'Gulfstream Park'
    country         TEXT,                            -- 'USA'
    surface_types   TEXT                             -- JSON list: ["Dirt","Turf","AllWeather"]
);

CREATE TABLE IF NOT EXISTS trainers (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT NOT NULL,                   -- canonical: "Ritvo, Katherine"
    normalized_name TEXT NOT NULL UNIQUE
);
CREATE INDEX IF NOT EXISTS idx_trainers_norm ON trainers(normalized_name);

CREATE TABLE IF NOT EXISTS jockeys (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT NOT NULL,                   -- canonical: "Saez, Luis"
    normalized_name TEXT NOT NULL UNIQUE
);
CREATE INDEX IF NOT EXISTS idx_jockeys_norm ON jockeys(normalized_name);

CREATE TABLE IF NOT EXISTS owners (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT NOT NULL,
    normalized_name TEXT NOT NULL UNIQUE
);
CREATE INDEX IF NOT EXISTS idx_owners_norm ON owners(normalized_name);

CREATE TABLE IF NOT EXISTS sires (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT NOT NULL,
    country         TEXT,                            -- (GB), (FR), etc — stripped from name
    normalized_name TEXT NOT NULL UNIQUE
);
CREATE INDEX IF NOT EXISTS idx_sires_norm ON sires(normalized_name);

CREATE TABLE IF NOT EXISTS dams (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT NOT NULL,
    country         TEXT,
    dam_sire_id     INTEGER REFERENCES sires(id),    -- "broodmare sire" / damsire
    normalized_name TEXT NOT NULL UNIQUE
);
CREATE INDEX IF NOT EXISTS idx_dams_norm ON dams(normalized_name);

CREATE TABLE IF NOT EXISTS horses (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT NOT NULL,                   -- canonical with apostrophes preserved
    country         TEXT,                            -- (GB), (FR), (IRE), etc
    normalized_name TEXT NOT NULL UNIQUE,
    color           TEXT,                            -- "Bay", "Chestnut", "Dark Bay or Brown", ...
    sex             TEXT,                            -- "Filly", "Mare", "Gelding", "Colt", "Horse"
    foaled_date     TEXT,                            -- YYYY-MM-DD when extractable
    foaled_place    TEXT,                            -- "Kentucky", "France", ...
    sire_id         INTEGER REFERENCES sires(id),
    dam_id          INTEGER REFERENCES dams(id),
    breeder_id      INTEGER REFERENCES owners(id)    -- breeders share the owners table
);
CREATE INDEX IF NOT EXISTS idx_horses_norm ON horses(normalized_name);
CREATE INDEX IF NOT EXISTS idx_horses_sire ON horses(sire_id);
CREATE INDEX IF NOT EXISTS idx_horses_dam ON horses(dam_id);

-- =====================================================================
-- Race day / race / entry — the fact tables.
-- =====================================================================

CREATE TABLE IF NOT EXISTS race_days (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    track_id        INTEGER NOT NULL REFERENCES tracks(id),
    race_date       TEXT NOT NULL,                   -- ISO YYYY-MM-DD
    source_pdf      TEXT,                            -- path of the chart PDF (for reproducibility)
    weather_summary TEXT,                            -- raw "Clear,79°" if uniform across card
    UNIQUE(track_id, race_date)
);
CREATE INDEX IF NOT EXISTS idx_race_days_date ON race_days(race_date);

CREATE TABLE IF NOT EXISTS races (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    race_day_id         INTEGER NOT NULL REFERENCES race_days(id),
    race_num            INTEGER NOT NULL,

    -- Distance + surface
    distance_text       TEXT,                        -- "Five And One Half Furlongs"
    distance_yards      INTEGER,                     -- normalized to yards (NULL if unparseable)
    surface             TEXT,                        -- "Dirt", "Turf", "AllWeather", "TapetaCourse"
    is_off_turf         INTEGER DEFAULT 0,           -- 1 if scheduled turf, moved to main
    track_condition     TEXT,                        -- "Fast", "Firm", "Sloppy", "Yielding", ...

    -- Money + conditions
    purse               INTEGER,                     -- USD
    available_money     INTEGER,
    value_of_race       INTEGER,
    value_breakdown     TEXT,                        -- "1st$12,600,2nd$5,210,..."
    race_type           TEXT,                        -- "CLAIMING", "MAIDEN SPECIAL WEIGHT", ...
    breed               TEXT,                        -- "Thoroughbred"
    class_level         TEXT,                        -- derived: claiming price, AOC, MSW level
    conditions_text     TEXT,                        -- full conditions paragraph (raw)
    claiming_price      INTEGER,                     -- top of claiming price range when applicable

    -- Track record reference
    track_record_holder TEXT,
    track_record_time   TEXT,
    track_record_date   TEXT,

    -- Field + scratches
    field_size          INTEGER,                     -- starters (after scratches)
    scratched_horses    TEXT,                        -- JSON list of {name, reason}

    -- Weather + start
    weather             TEXT,                        -- "Clear"
    temperature_f       INTEGER,                     -- 79
    off_at              TEXT,                        -- "12:41"
    start_note          TEXT,                        -- "Good for all" / "Good for all except 2,5"
    timing_method       TEXT,                        -- "Electronic" / "Video Review" / NULL

    -- Times
    call_labels         TEXT,                        -- JSON: ["Start","1/4","3/8","Str","Fin"]
    fractional_times    TEXT,                        -- JSON list of strings ["22.56","46.23",...]
    final_time          TEXT,                        -- "1:05.90"
    time_from_gate      TEXT,                        -- "1:03.65" if present, else NULL
    split_times         TEXT,                        -- JSON list ["23:67","12:98","6:69"]
    run_up_feet         INTEGER,
    temporary_rail_feet INTEGER,                     -- NULL when no temp rail set

    -- Pool + footnotes
    total_wps_pool      INTEGER,
    footnotes           TEXT,                        -- raw race narrative (preserve original)

    UNIQUE(race_day_id, race_num)
);
CREATE INDEX IF NOT EXISTS idx_races_day ON races(race_day_id);
CREATE INDEX IF NOT EXISTS idx_races_surface ON races(surface);
CREATE INDEX IF NOT EXISTS idx_races_type ON races(race_type);

CREATE TABLE IF NOT EXISTS entries (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    race_id             INTEGER NOT NULL REFERENCES races(id),
    horse_id            INTEGER NOT NULL REFERENCES horses(id),
    jockey_id           INTEGER REFERENCES jockeys(id),
    trainer_id          INTEGER REFERENCES trainers(id),
    owner_id            INTEGER REFERENCES owners(id),

    -- Program + post
    program_num         TEXT,                        -- can be "1A", "1B" so TEXT
    post_pos            INTEGER,                     -- starting gate post
    start_pos           INTEGER,                     -- "Start" column (relative position out of gate)

    -- Conditions of running
    weight_lbs          INTEGER,
    equipment           TEXT,                        -- raw code "Lbf"
    has_lasix           INTEGER,                     -- derived: 'L' in equipment
    has_blinkers        INTEGER,                     -- derived: 'b' or 'B'
    has_front_bandages  INTEGER,                     -- derived: 'f' or 'F'
    first_time_blinkers INTEGER,                     -- derived: 'B' (uppercase)
    first_time_bandages INTEGER,                     -- derived: 'F'

    -- Pace + result
    pace_calls_json     TEXT,                        -- JSON {"Start":"7","1/4":"64","3/8":"41/2",...}
                                                     -- preserves raw "<pos><margin>" tokens
    finish_pos          INTEGER,                     -- official finish (1-based), NULL if DQ/DNF
    finish_status       TEXT,                        -- 'finished', 'DNF', 'DQ' etc when noted
    beaten_lengths      REAL,                        -- lengths back from leader, NULL if winner/DNF
    winning_margin_text TEXT,                        -- raw margin from leader (Head/Neck/Nose/N)

    -- Anchor signals
    final_odds          REAL,                        -- 2.20  — Benter anchor, very high coverage
    is_favorite         INTEGER DEFAULT 0,           -- '*' flag on odds in chart

    -- Optional signals
    speed_figure        INTEGER,                     -- Equibase Rating when present; NULL otherwise
    trip_comment        TEXT,                        -- raw "bidtightqtrs,bmpd1/8"
    last_raced_raw      TEXT,                        -- "5Dec189GP2" — parse in later phase

    -- Wagering / claiming
    win_payout          REAL,                        -- $2 base, only for top 3
    place_payout        REAL,
    show_payout         REAL,
    claimed_in_race     INTEGER DEFAULT 0,           -- horse was claimed out of this race
    new_trainer_after   TEXT,                        -- if claimed, claiming barn
    new_owner_after     TEXT,
    claiming_price      INTEGER,                     -- this horse's claiming tag (may differ)

    UNIQUE(race_id, program_num)
);
CREATE INDEX IF NOT EXISTS idx_entries_race ON entries(race_id);
CREATE INDEX IF NOT EXISTS idx_entries_horse ON entries(horse_id);
CREATE INDEX IF NOT EXISTS idx_entries_jockey ON entries(jockey_id);
CREATE INDEX IF NOT EXISTS idx_entries_trainer ON entries(trainer_id);
CREATE INDEX IF NOT EXISTS idx_entries_finish ON entries(finish_pos);

-- =====================================================================
-- Exotic wagers — denormalized by row of the payouts table.
-- =====================================================================

CREATE TABLE IF NOT EXISTS exotic_payouts (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    race_id         INTEGER NOT NULL REFERENCES races(id),
    wager_type      TEXT NOT NULL,                   -- "$1.00 Exacta", "$0.50 Pick3", ...
    base_amount     REAL,                            -- 1.00, 0.50, 0.10
    wager_name      TEXT,                            -- "Exacta", "Pick3", "Super High Five"
    winning_numbers TEXT,                            -- "4-6-1-3"
    qualifier       TEXT,                            -- "(3correct)" / "(4correct)" / NULL
    payoff          REAL,                            -- 53.99 (NULL if no payoff)
    pool            INTEGER,                         -- $ in pool
    carryover       INTEGER                          -- when present
);
CREATE INDEX IF NOT EXISTS idx_exotic_race ON exotic_payouts(race_id);

-- =====================================================================
-- Provenance: per-PDF processing log so we can re-run, skip, or audit.
-- =====================================================================

CREATE TABLE IF NOT EXISTS parsed_files (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    source_pdf      TEXT NOT NULL UNIQUE,
    file_sha256     TEXT,
    parsed_at       TEXT NOT NULL,                   -- ISO timestamp
    parser_version  TEXT NOT NULL,
    races_found     INTEGER,
    races_loaded    INTEGER,
    success         INTEGER NOT NULL,                -- 0/1
    error_message   TEXT,
    warnings_json   TEXT                             -- JSON array of warning strings
);
CREATE INDEX IF NOT EXISTS idx_parsed_files_sha ON parsed_files(file_sha256);
