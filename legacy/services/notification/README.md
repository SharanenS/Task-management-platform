# Notification Service

Notification Service owns durable, recipient-private in-application notifications and its
source-event inbox. It consumes versioned task-assignment and report-terminal events from
durable RabbitMQ queues. Delivery is at least once; recipient/event uniqueness prevents
duplicate logical notifications.

Only the Gateway may use the internal inbox API. Administrators do not receive implicit
access to another employee's notifications.
