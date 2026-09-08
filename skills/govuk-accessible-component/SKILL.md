---
name: govuk-accessible-component
description: >-
  Build an accessible GOV.UK Design System component or pattern (for example a
  form input, error summary, button, or notification banner) that meets WCAG 2.2
  AA and the GDS accessibility expectations. Use this skill when a task asks to
  create, refactor, or review a GOV.UK / GDS frontend component and needs correct
  semantic HTML, Nunjucks macro usage, keyboard operability, visible focus, and
  screen-reader-friendly labelling and error handling.
license: MIT
metadata:
  domain: frontend
  design-system: govuk-design-system
  wcag-target: "2.2 AA"
---

# Build an accessible GOV.UK Design System component

## When to use this skill

Use this skill when a task involves creating, refactoring, or reviewing a
frontend component or pattern that should follow the GOV.UK Design System (GDS)
and be accessible to all users, including those using assistive technology.

Typical triggers:

- "Build a GOV.UK text input with a label and hint."
- "Create an accessible error summary for this form."
- "Add a GDS-style notification banner."
- "Review this component for WCAG 2.2 AA compliance."

## Non-negotiable accessibility expectations

Every component produced with this skill MUST satisfy the following. Treat these
as acceptance criteria, not suggestions.

1. **Semantic HTML first.** Use native elements (`<button>`, `<a>`, `<label>`,
   `<fieldset>`, `<legend>`, `<input>`) before reaching for ARIA. Do not use a
   `<div>` with a click handler where a `<button>` belongs.
2. **Every control has a programmatic name.** Inputs are associated with a
   `<label>` via `for`/`id`. Groups of related controls (radios, checkboxes,
   date parts) are wrapped in a `<fieldset>` with a `<legend>`.
3. **Hints and errors are linked with `aria-describedby`.** A field's hint text
   and its error message are referenced from the input's `aria-describedby` so
   screen readers announce them.
4. **Errors are surfaced twice.** An `govuk-error-summary` at the top of the
   page (focused on submit) links to each errored field, and each field shows an
   inline `govuk-error-message`. The page `<title>` is prefixed with "Error: "
   on a failed submit.
5. **Keyboard operable.** All interactive elements are reachable and operable
   with the keyboard alone, in a logical tab order, with no keyboard traps.
6. **Visible focus.** Do not remove the GDS focus style. Focus indicators must
   remain visible (the yellow focus highlight).
7. **Colour and contrast.** Do not convey meaning by colour alone. Text and UI
   components meet WCAG 2.2 AA contrast. Use GDS colours/classes rather than
   ad-hoc values.
8. **Touch target and spacing.** Interactive targets follow GDS sizing; do not
   shrink targets below the design system's defaults.
9. **Progressive enhancement.** The component works without JavaScript; JS only
   enhances. Never rely on JS for the core task to be completable.
10. **Language and clarity.** Labels, hints, and error messages use plain
    English and follow the GDS content style (specific, actionable error text
    such as "Enter your date of birth").

## How to build the component

Follow these steps in order.

### 1. Identify the correct GDS component

Match the task to an existing GOV.UK Design System component or pattern
(text input, character count, radios, checkboxes, date input, select, button,
error summary, notification banner, etc.). Prefer an existing component over a
bespoke one. If the design system has a documented pattern, follow it.

### 2. Prefer the Nunjucks macro

If a GOV.UK Frontend Nunjucks macro exists for the component, use it and pass the
correct options rather than hand-writing markup. Macros already encode the
accessible structure (label association, hint/error wiring, classes).

```njk
{% from "govuk/components/input/macro.njk" import govukInput %}

{{ govukInput({
  label: { text: "What is your name?" },
  id: "full-name",
  name: "fullName",
  hint: { text: "As it appears on your passport" }
}) }}
```

### 3. If hand-writing HTML, use the GDS structure

When a macro is unavailable, reproduce the accessible structure exactly:

```html
<div class="govuk-form-group">
  <label class="govuk-label" for="full-name">
    What is your name?
  </label>
  <div id="full-name-hint" class="govuk-hint">
    As it appears on your passport
  </div>
  <input
    class="govuk-input"
    id="full-name"
    name="fullName"
    type="text"
    aria-describedby="full-name-hint"
    autocomplete="name"
  />
</div>
```

### 4. Wire up errors accessibly

On a validation failure:

- Add `govuk-form-group--error` to the form group.
- Add a `<span class="govuk-error-message">` with a visually hidden "Error:"
  prefix, referenced from the input's `aria-describedby` (alongside the hint id).
- Render a `govukErrorSummary` at the top of the page linking to each errored
  field by fragment id, and move focus to it on submit.
- Prefix the page `<title>` with `Error: `.

```html
<div class="govuk-form-group govuk-form-group--error">
  <label class="govuk-label" for="full-name">What is your name?</label>
  <p id="full-name-error" class="govuk-error-message">
    <span class="govuk-visually-hidden">Error:</span> Enter your name
  </p>
  <input
    class="govuk-input govuk-input--error"
    id="full-name"
    name="fullName"
    type="text"
    aria-describedby="full-name-error"
  />
</div>
```

### 5. Self-check before finishing

Run through the checklist in `references/accessibility-checklist.md`. Do not
report the component as complete until every applicable item passes.

## Output format

When producing a component, return:

1. The component markup (Nunjucks macro call and/or HTML).
2. A short note of which GDS component/pattern it maps to.
3. The accessibility features you implemented, mapped to the expectations above.
4. Any assumptions (e.g., field names, autocomplete tokens).

## References

- `references/accessibility-checklist.md` — the WCAG 2.2 AA / GDS self-check
  list to run before declaring a component done.
