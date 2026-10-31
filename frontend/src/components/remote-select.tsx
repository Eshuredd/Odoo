"use client";
import { useCallback, useEffect, useId, useRef, useState } from "react";
import { ChevronDown } from "lucide-react";
import { useResource } from "@/lib/hooks";
import type { Page } from "@/lib/types";
import { Button, Loading, Notice } from "./ui";

export function RemoteSelect<T extends { id: number }>({
  label,
  value,
  onChange,
  load,
  describe,
  searchable = true,
  optional = false,
}: {
  label: string;
  value: T | null;
  onChange: (value: T | null) => void;
  load: (
    search: string,
    offset: number,
    signal: AbortSignal,
  ) => Promise<Page<T>>;
  describe: (value: T) => string;
  searchable?: boolean;
  optional?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState("");
  const [offset, setOffset] = useState(0);
  const root = useRef<HTMLDivElement>(null);
  const id = useId();
  useEffect(() => {
    if (!open) return;
    function outside(event: MouseEvent) {
      if (!root.current?.contains(event.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", outside);
    return () => document.removeEventListener("mousedown", outside);
  }, [open]);
  return (
    <div
      className="remote-select"
      ref={root}
      onKeyDown={(event) => {
        if (event.key === "Escape") {
          setOpen(false);
          root.current?.querySelector<HTMLButtonElement>("button")?.focus();
        }
      }}
    >
      <button
        type="button"
        aria-label={label}
        aria-expanded={open}
        aria-controls={id}
        className="remote-trigger"
        onClick={() => setOpen(!open)}
      >
        {value ? describe(value) : `Select ${label.toLowerCase()}`}
        <ChevronDown size={14} />
      </button>
      {optional && value && (
        <button
          type="button"
          className="remote-clear"
          onClick={() => onChange(null)}
        >
          Clear {label.toLowerCase()}
        </button>
      )}
      {open && (
        <div
          id={id}
          className="remote-dropdown"
          aria-label={`${label} options`}
        >
          {searchable && (
            <input
              autoFocus
              aria-label={`Search ${label.toLowerCase()}`}
              value={search}
              placeholder={`Search ${label.toLowerCase()}…`}
              onChange={(event) => {
                setSearch(event.target.value);
                setOffset(0);
              }}
            />
          )}
          <RemoteOptions
            load={load}
            search={search}
            offset={offset}
            setOffset={setOffset}
            describe={describe}
            select={(item) => {
              onChange(item);
              setOpen(false);
              root.current?.querySelector<HTMLButtonElement>("button")?.focus();
            }}
          />
        </div>
      )}
    </div>
  );
}
function RemoteOptions<T extends { id: number }>({
  load,
  search,
  offset,
  setOffset,
  describe,
  select,
}: {
  load: (
    search: string,
    offset: number,
    signal: AbortSignal,
  ) => Promise<Page<T>>;
  search: string;
  offset: number;
  setOffset: (offset: number) => void;
  describe: (value: T) => string;
  select: (value: T) => void;
}) {
  const result = useResource(
    useCallback(
      (signal) => load(search, offset, signal),
      [load, search, offset],
    ),
  );
  if (result.loading) return <Loading label="Loading options…" />;
  if (result.error)
    return (
      <Notice>
        {result.error}
        <Button onClick={result.reload}>Retry</Button>
      </Notice>
    );
  return (
    <>
      {result.data?.items.map((item) => (
        <button
          className="remote-option"
          type="button"
          key={item.id}
          onClick={() => select(item)}
        >
          {describe(item)}
        </button>
      ))}
      {!result.data?.items.length && (
        <p className="muted p-3 text-xs">
          No matching records. Ask an administrator to configure the catalog or
          customer account.
        </p>
      )}
      <div className="remote-pages">
        <Button
          type="button"
          aria-label="Previous options"
          disabled={offset === 0}
          onClick={() => setOffset(Math.max(0, offset - 10))}
        >
          Previous
        </Button>
        <span>{result.data?.total || 0} records</span>
        <Button
          type="button"
          aria-label="Next options"
          disabled={offset + 10 >= (result.data?.total || 0)}
          onClick={() => setOffset(offset + 10)}
        >
          Next
        </Button>
      </div>
    </>
  );
}
