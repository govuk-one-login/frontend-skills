# skills-store

## ADDED Requirements

### Requirement: Skills follow the open Agent Skills specification
The system SHALL store agent skills under `skills/<skill-name>/`, where each
skill is a directory containing a `SKILL.md` file conforming to the open Agent
Skills specification, with optional `scripts/`, `references/`, and `assets/`
directories.

#### Scenario: A new skill is added
- **WHEN** a contributor adds a new skill directory under `skills/`
- **THEN** the directory contains a `SKILL.md` file with YAML frontmatter
  followed by a Markdown body

#### Scenario: Optional resource directories are permitted
- **WHEN** a skill needs supporting scripts, reference docs, or static assets
- **THEN** it may include `scripts/`, `references/`, and/or `assets/`
  subdirectories, and the skill remains valid

### Requirement: SKILL.md frontmatter is valid
The system SHALL require each `SKILL.md` to include the required frontmatter
fields `name` and `description`, where `name` is 1–64 characters of lowercase
alphanumeric characters and hyphens (no leading/trailing hyphen, no consecutive
hyphens) and `description` is 1–1024 non-empty characters. Optional fields
`license`, `compatibility`, `metadata`, and `allowed-tools` MAY be present.

#### Scenario: Frontmatter has the required fields
- **WHEN** a skill's `SKILL.md` is validated
- **THEN** it contains non-empty `name` and `description` fields that satisfy
  the length and character constraints

#### Scenario: Frontmatter is missing a required field
- **WHEN** a skill's `SKILL.md` omits `name` or `description`
- **THEN** the skill is invalid

### Requirement: Skill name matches its directory
The system SHALL require the `name` frontmatter field to exactly match the
skill's parent directory name.

#### Scenario: Name matches the directory
- **WHEN** a skill directory is `skills/govuk-accessible-component/`
- **THEN** its `SKILL.md` `name` is `govuk-accessible-component`

#### Scenario: Name does not match the directory
- **WHEN** a skill's `name` frontmatter differs from its parent directory name
- **THEN** the skill is invalid

### Requirement: Seed exemplar skill is GDS-flavoured and accessibility-focused
The system SHALL include a seed exemplar skill named
`govuk-accessible-component` that targets a GOV.UK Design System component or
pattern and states explicit accessibility expectations.

#### Scenario: Exemplar skill is present
- **WHEN** the repository is inspected
- **THEN** `skills/govuk-accessible-component/SKILL.md` exists, references the
  GOV.UK Design System, and documents accessibility expectations for the
  component it produces
