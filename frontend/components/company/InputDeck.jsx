"use client";

import { producedBy } from "@/data/agents";

/* The left half of the stage: where the creator actually types.
   `needs` are inputs that come from an earlier agent rather than from the
   form, so they render as loaded/missing reels instead of empty fields. */
export default function InputDeck({ agent, values, files, onChange, onFile, state }) {
  return (
    <div className="deck">
      <h4 className="deck__cap">Input</h4>

      {agent.needs.length > 0 && (
        <ul className="reels">
          {agent.needs.map((field) => {
            const loaded = Boolean(state[field]);
            return (
              <li key={field} className={`reel-chip${loaded ? " is-loaded" : ""}`}>
                <span className="reel-chip__dot" aria-hidden="true" />
                <span>
                  <b>{field}</b>
                  {loaded
                    ? ` loaded from ${producedBy[field]}`
                    : ` — run ${producedBy[field]} first`}
                </span>
              </li>
            );
          })}
        </ul>
      )}

      <div className="fields">
        {agent.fields.map((field) => {
          const id = `${agent.key}-${field.name}`;
          const value = values[field.name] ?? "";

          if (field.type === "chips") {
            const picked = Array.isArray(value) ? value : [];
            return (
              <fieldset className="field field--wide" key={field.name}>
                <legend className="field__label">{field.label}</legend>
                <div className="chips">
                  {field.options.map((option) => {
                    const on = picked.includes(option);
                    return (
                      <button
                        type="button"
                        key={option}
                        className={`chip-pick${on ? " is-on" : ""}`}
                        aria-pressed={on}
                        onClick={() =>
                          onChange(
                            field.name,
                            on ? picked.filter((p) => p !== option) : [...picked, option]
                          )
                        }
                      >
                        {option}
                      </button>
                    );
                  })}
                </div>
              </fieldset>
            );
          }

          return (
            <p
              className={`field${
                field.type === "textarea" || field.type === "file" ? " field--wide" : ""
              }`}
              key={field.name}
            >
              <label className="field__label" htmlFor={id}>
                {field.label}
                {field.required && <i aria-hidden="true"> *</i>}
              </label>

              {field.type === "textarea" && (
                <textarea
                  id={id}
                  rows={2}
                  value={value}
                  placeholder={field.placeholder}
                  onChange={(e) => onChange(field.name, e.target.value)}
                />
              )}

              {field.type === "select" && (
                <select id={id} value={value} onChange={(e) => onChange(field.name, e.target.value)}>
                  {field.options.map((option) => (
                    <option key={option} value={option}>
                      {option}
                    </option>
                  ))}
                </select>
              )}

              {field.type === "file" && (
                <span className="field__file">
                  <input
                    id={id}
                    type="file"
                    accept={field.accept}
                    onChange={(e) => onFile(field.name, e.target.files?.[0] || null)}
                  />
                  <span>{files[field.name]?.name || "No file chosen"}</span>
                </span>
              )}

              {(field.type === "text" || field.type === "number") && (
                <input
                  id={id}
                  type={field.type}
                  value={value}
                  placeholder={field.placeholder}
                  onChange={(e) => onChange(field.name, e.target.value)}
                />
              )}
            </p>
          );
        })}
      </div>
    </div>
  );
}
