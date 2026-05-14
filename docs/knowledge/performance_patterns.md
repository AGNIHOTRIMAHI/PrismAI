# Performance Best Practices

## Algorithm Complexity
Prefer O(n log n) over O(n²). Use hash maps for O(1) lookups.

## Database Queries
Use pagination; never `SELECT *` in production.
Batch inserts instead of looping individual INSERTs.
Add composite indexes for multi-column WHERE / ORDER BY.

## Caching
Cache expensive computations with TTL-based invalidation.
Use Redis for shared cache in distributed systems.

## Python Specifics
Use generators for large sequences to avoid memory spikes.
Profile with cProfile / py-spy before optimising.
