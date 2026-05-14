# Clean Code Principles

## Meaningful Names
Variable names should reveal intent. `elapsed_time_in_days` beats `d`.

## Functions
Functions should do ONE thing. Ideal length: fewer than 20 lines. Max arguments: 3.

## DRY
Duplicate logic is a maintenance time-bomb. Extract shared logic into helpers.

## Error Handling
Prefer exceptions to error codes. Never swallow exceptions silently.

## Comments
Code should be self-documenting. Comments explain *why*, not *what*.
