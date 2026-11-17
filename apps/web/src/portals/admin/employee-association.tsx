"use client";
import { useState } from "react";
export function EmployeeAssociation({
  employees,
  initialId = "",
}: {
  employees: { id: string; displayName: string }[];
  initialId?: string;
}) {
  const [id, setId] = useState(
    employees.some((e) => e.id === initialId) ? initialId : "",
  );
  const person = employees.find((e) => e.id === id);
  return (
    <>
      <label>
        Employee record
        <select
          aria-label="Employee record"
          name="employeeId"
          value={id}
          onChange={(event) => setId(event.target.value)}
        >
          <option value="">Create a new employee record</option>
          {employees.map((e) => (
            <option key={e.id} value={e.id}>
              {e.displayName}
            </option>
          ))}
        </select>
      </label>
      <label>
        Full name
        <input
          key={id}
          name="displayName"
          required
          maxLength={150}
          defaultValue={person?.displayName ?? ""}
          readOnly={!!person}
          autoComplete="off"
        />
      </label>
    </>
  );
}
