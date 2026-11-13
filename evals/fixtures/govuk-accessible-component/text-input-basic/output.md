```njk
{% from "govuk/components/input/macro.njk" import govukInput %}

{{ govukInput({
  label: { text: "What is your full name?" },
  id: "full-name",
  name: "fullName",
  hint: { text: "As it appears on your passport" }
}) }}

# This component maps to the GOV.UK Design System text input pattern.

## Accessibility Features Implemented:
1. **Semantic HTML first.** The `govukInput` macro uses native `<input>`, `<label>`, and `<div>` elements.
2. **Every control has a programmatic name.** The `for` attribute links the label to the input.
3. **Hints and errors are linked with `aria-describedby`.** The hint is referenced from the input's `aria-describedby`.
4. **Keyboard operable.** The component is keyboard operable with a logical tab order.
5. **Visible focus.** The GDS focus style is applied and remains visible.
6. **Colour and contrast.** The component uses GDS colours and meets WCAG 2.2 AA contrast.
7. **Touch target and spacing.** The input field follows GDS sizing.
8. **Progressive enhancement.** The component works without JavaScript.
9. **Language and clarity.** The label and hint use plain English.
```