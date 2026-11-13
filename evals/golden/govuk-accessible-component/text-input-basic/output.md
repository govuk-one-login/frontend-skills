```njk
{% from "govuk/components/input/macro.njk" import govukInput %}

{{ govukInput({
  label: { text: "What is your full name?" },
  id: "full-name",
  name: "fullName",
  hint: { text: "As it appears on your passport" }
}) }}
```

Equivalent hand-written GOV.UK Design System markup:

```html
<div class="govuk-form-group">
  <label class="govuk-label" for="full-name">
    What is your full name?
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

This component maps to the GOV.UK Design System text input pattern.

### Accessibility features implemented

1. **Semantic HTML first:** a native `<label>` is associated with the `<input>`
   via matching `for`/`id`.
2. **Programmatic name:** the input's accessible name comes from the associated
   label.
3. **Hint linked with `aria-describedby`:** the hint's `id` is referenced from
   the input's `aria-describedby` so screen readers announce it.
4. **Visible focus:** the GDS focus style is preserved (not removed).
5. **Keyboard operable:** the native input is fully keyboard operable in a
   logical tab order.
6. **Colour and contrast:** GOV.UK Design System classes meet WCAG 2.2 AA.
7. **Progressive enhancement:** the component works without JavaScript.
8. **Language and clarity:** the label and hint use plain English.

Field name: `fullName`. Autocomplete token: `name`.
