import "./postgres.css";
import html from "./postgres.html";
//import * as MONACO_VS from "monaco-editor";
import type { RenderContext } from "@anywidget/types";
import { generateUUID } from "./uuid";
//import { PGlite } from "@electric-sql/pglite";
//import * as PGlite from "https://esm.sh/@electric-sql/pglite";
//import PGlite from "https://cdn.jsdelivr.net/npm/@electric-sql/pglite/dist/pglite.min.js";
import { PGlite } from "https://cdn.jsdelivr.net/npm/@electric-sql/pglite/dist/index.js";
//import PGlite from "https://cdn.jsdelivr.net/npm/@electric-sql/pglite@0.1.5/+esm";

interface WidgetModel {
  code_content: string;
  response: {};
}

const DEFAULT_SQL = `
-- Optionally select statements to execute.

CREATE TABLE IF NOT EXISTS test  (
        id serial primary key,
        title varchar not null
      );

INSERT INTO test (title) values ('dummy');

`.trim();

function formatTable(result: {
  rows: any[];
  fields: { name: string; dataTypeID: number }[];
}): HTMLTableElement {
  const table = document.createElement("table");

  const headerRow = table.insertRow();
  result.fields.forEach((field) => {
    const th = document.createElement("th");
    th.textContent = field.name;
    headerRow.appendChild(th);
  });
  return table;
}

function formatRows(
  result: { rows: any[]; fields: { name: string; dataTypeID: number }[] },
  table: HTMLTableElement
): void {
  result.rows.forEach((row) => {
    const tr = table.insertRow();
    result.fields.forEach((field) => {
      const cell = tr.insertCell();
      cell.textContent = String(row[field.name]);
    });
  });
}

function render({ model, el }: RenderContext<WidgetModel>) {
  // Initialize PGlite
  const idb = model.get("idb");
  const db =  idb ? new PGlite(idb) : new PGlite();

  const _headless = model.get("headless");

  if (!_headless) {
    let el2 = document.createElement("div");
    el2.innerHTML = html;
    const uuid = generateUUID();
    el2.id = uuid;
    el.appendChild(el2);
  }

  //const runButton = el.querySelector('button[name="run-button"]');

  model.on("change:code_content", async () => {
    const sql = model.get("code_content");
    const response = await db.query(sql);
    model.set("response", response);

    if (!_headless) {
      const codeEditor = el.querySelector('div[title="code-editor"]');
      const output = el.querySelector('div[title="output"]');
      const results = el.querySelector('div[title="results"]');

      codeEditor.innerHTML =
        codeEditor.innerHTML + "<br>" + model.get("code_content");

      output.innerHTML = JSON.stringify(response);
      const table = formatTable(response);
      formatRows(response, table);
      results.innerHTML = "";
      results.append(table);
    }

    model.save_changes();
  });
}

export default { render };
