# Work Management Service (future phase)

Owns projects, project membership, tasks, comments, and activity history.
Introduced in Phase 4. Employee identifiers are references, never cross-database
foreign keys. Owns its database, migrations, resource authorization, and outbox.
No running service or tables are created in Phase 1.
