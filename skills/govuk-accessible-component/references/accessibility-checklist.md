# Accessibility checklist (WCAG 2.2 AA + GDS)

Run this checklist before declaring a GOV.UK Design System component complete.
Each item is pass/fail; a component is done only when every applicable item
passes.

## Structure and semantics

- [ ] Native semantic elements are used (`button`, `a`, `label`, `fieldset`,
      `legend`, `input`) before any ARIA.
- [ ] ARIA is only used to fill genuine gaps, and no ARIA contradicts the native
      semantics.
- [ ] Heading levels are logical and not skipped.

## Labels, hints, and grouping

- [ ] Every input has a `<label>` associated via `for`/`id`.
- [ ] Hint text has an `id` referenced from the input's `aria-describedby`.
- [ ] Related controls (radios, checkboxes, multi-part date) are wrapped in a
      `<fieldset>` with a descriptive `<legend>`.
- [ ] `autocomplete` tokens are set on personal-data fields where appropriate.

## Errors

- [ ] A `govukErrorSummary` appears at the top of the page on a failed submit
      and links to each errored field by fragment id.
- [ ] Focus moves to the error summary on submit.
- [ ] Each errored field has an inline `govuk-error-message` with a visually
      hidden "Error:" prefix.
- [ ] The error message id is included in the input's `aria-describedby`.
- [ ] The page `<title>` is prefixed with "Error: " on a failed submit.
- [ ] Error text is specific and actionable (e.g. "Enter your date of birth",
      not "Invalid input").

## Keyboard and focus

- [ ] All interactive elements are reachable and operable by keyboard alone.
- [ ] Tab order is logical and matches the visual order.
- [ ] There are no keyboard traps.
- [ ] The GDS visible focus style is preserved (not removed via `outline: none`
      without a replacement).

## Colour, contrast, and layout

- [ ] Meaning is never conveyed by colour alone.
- [ ] Text and UI components meet WCAG 2.2 AA contrast ratios.
- [ ] GDS colour classes/tokens are used rather than ad-hoc colour values.
- [ ] Interactive target sizes follow GDS defaults.

## Progressive enhancement

- [ ] The core task can be completed without JavaScript.
- [ ] JavaScript only enhances; it is not required for the component to function.

## Content

- [ ] Labels, hints, and errors use plain English and follow GDS content style.

## References

- GOV.UK Design System: https://design-system.service.gov.uk/
- GOV.UK Frontend: https://github.com/alphagov/govuk-frontend
- WCAG 2.2: https://www.w3.org/TR/WCAG22/
