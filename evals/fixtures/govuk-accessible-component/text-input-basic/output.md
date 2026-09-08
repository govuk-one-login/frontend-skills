# Accessible GOV.UK text input — full name

## Component (Nunjucks macro)

```njk
{% from "govuk/components/input/macro.njk" import govukInput %}

{{ govukInput({
  label: {
    text: "What is your full name?"
  },
  id: "full-name",
  name: "fullName",
  hint: {
    text: "As it appears on your passport or driving licence"
  },
  autocomplete: "name"
}) }}
```

## Equivalent HTML (if a macro is unavailable)

```html
<div class="govuk-form-group">
  <label class="govuk-label" for="full-name">
    What is your full name?
  </label>
  <div id="full-name-hint" class="govuk-hint">
    As it appears on your passport or driving licence
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

## GDS component mapping

This maps to the GOV.UK Design System **Text input** component, used inside a
`govuk-form-group`.

## Accessibility features implemented

- **Programmatic name:** a native `<label>` is associated with the input via
  matching `for="full-name"` and `id="full-name"`.
- **Hint association:** the hint text has `id="full-name-hint"` and is referenced
  from the input's `aria-describedby`, so screen readers announce it.
- **GDS classes:** uses `govuk-form-group`, `govuk-label`, `govuk-hint`, and
  `govuk-input` rather than ad-hoc styling.
- **Visible focus:** the default GDS focus style is preserved (no `outline: none`
  and no overrides), keeping the yellow focus highlight.
- **Autocomplete:** `autocomplete="name"` helps users complete the field faster.
- **Progressive enhancement:** the field works with no JavaScript.

## Assumptions

- Field name is `fullName`; adjust to match your form model.
- No validation error state is shown here; on a failed submit, add
  `govuk-form-group--error`, an inline `govuk-error-message`, an error summary,
  and an `Error: ` title prefix as described in the skill.
