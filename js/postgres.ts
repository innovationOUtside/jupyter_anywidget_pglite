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
  datadump: string;
  code_content: string;
  response: any;
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
interface Response {
  rows: any[]; // Array of any type
  fields: {
    name: string;
    dataTypeID: number;
  }[];
}

function formatRows(result: Response, table: HTMLTableElement): void {
  result.rows.forEach((row) => {
    const tr = table.insertRow();
    result.fields.forEach((field) => {
      const cell = tr.insertCell();
      cell.textContent = String(row[field.name]);
    });
  });
}

// Via claude.ai
function createFileObj(file_package) {
  if (
    file_package &&
    file_package.file_content &&
    file_package.file_info
  ) {
    const { file_content, file_info } = file_package;

    const byteCharacters = atob(file_content);
    const byteNumbers = new Array(byteCharacters.length);
    for (let i = 0; i < byteCharacters.length; i++) {
      byteNumbers[i] = byteCharacters.charCodeAt(i);
    }
    const byteArray = new Uint8Array(byteNumbers);

    // Create a Blob first
    const blob = new Blob([byteArray], { type: file_info.type });

    // Create a File from the Blob
    const file = new File([blob], file_info.name, {
      type: file_info.type,
      lastModified: file_info.lastModified,
    });

    return file;
  }
  return null;
}

function render({ model, el }: RenderContext<WidgetModel>) {
  // Initialize PGlite
  const idb = model.get("idb");
  const file_data = model.get("file_package");
  const data = createFileObj(file_data);
  const options = {} as any;
  if (data) options.loadDataDir = data;

  const db = idb ? new PGlite(idb, options) : new PGlite(options);
  const _headless = model.get("headless");

  if (!_headless) {
    let el2 = document.createElement("div");
    el2.innerHTML = html;
    const uuid = generateUUID();
    el2.id = uuid;
    el.appendChild(el2);
  }

  //const runButton = el.querySelector('button[name="run-button"]');

  model.on("change:datadump", async () => {
    const datadump = model.get("datadump");
    if (datadump == "generate_dump") {
      let dumpfile = await db.dumpDataDir();
      const reader = new FileReader();
      reader.onload = (e) => {
        // Update file_info with serializable data
        const file_info = {
          name: dumpfile.name,
          size: dumpfile.size,
          type: dumpfile.type,
          lastModified: dumpfile.lastModified,
        };

        const file_content = e.target.result.split(",")[1]; // Get base64 part

        const file_package = {
          file_info: file_info,
          file_content: file_content,
        };

        model.set("file_package", file_package);
        model.save_changes();
      };
      reader.readAsDataURL(dumpfile);
    }
  });

  model.on("change:code_content", async () => {
    function queryDisplay(q) {
      const codeEditor = el.querySelector('div[title="code-editor"]');
      codeEditor.innerHTML = codeEditor.innerHTML + "<br>" + q;
    }
    function resultDisplay(response) {
      const output = el.querySelector('div[title="output"]');
      const results = el.querySelector('div[title="results"]');

      output.innerHTML = JSON.stringify(response);
      const table = formatTable(response);
      formatRows(response, table);
      results.innerHTML = "";
      results.append(table);
    }

    function fullDisplay(q, r) {
      if (!_headless) {
        queryDisplay(q);
        resultDisplay(r);
      }
    }

    const sql = model.get("code_content");
    const multiline = model.get("multiline");
    const multiexec = model.get("multiexec");
    let response: Response = {
      rows: [], // Initialize empty array
      fields: [
        {
          name: "", // Initialize empty string
          dataTypeID: 0, // Initialize to some default number
        },
      ],
    };
    if (multiexec) {
      queryDisplay(sql);
      let multi_response = await db.exec(sql);
      // for now, just display the final item
      resultDisplay(multi_response[multi_response.length - 1]);
      model.set("response", {
        response: multi_response,
        response_type: "multi",
      });
    } else if (multiline != "") {
      const items = sql.split(multiline); // Splits the string into an array

      for (const item of items) {
        const q = item.trim();
        if (q !== "") {
          queryDisplay(`${q};`);
          response = await db.query(q);
          resultDisplay(response);
        }
      }
      model.set("response", { response: response, response_type: "single" });
    } else {
      queryDisplay(sql);
      response = await db.query(sql);
      resultDisplay(response);
      model.set("response", { response: response, response_type: "single" });
    }

    model.save_changes();
  });
}

export default { render };
