import "./postgres.css";
import html from "./postgres.html";
//import { PGlite } from "@electric-sql/pglite";
import { PGlite } from "https://cdn.jsdelivr.net/npm/@electric-sql/pglite/dist/index.js";
import { generateUUID } from "./uuid";
import { play_success, play_error } from "./audio";

const DEFAULT_SQL = `
-- Optionally select statements to execute.

CREATE TABLE IF NOT EXISTS test  (
        id serial primary key,
        title varchar not null
      );

INSERT INTO test (title) values ('dummy');

`.trim();

function formatTable(result) {
  const table = document.createElement("table");

  const headerRow = table.insertRow();
  result.fields.forEach((field) => {
    const th = document.createElement("th");
    th.textContent = field.name;
    headerRow.appendChild(th);
  });
  return table;
}

function formatRows(result, table) {
  result.rows.forEach((row) => {
    const tr = table.insertRow();
    result.fields.forEach((field) => {
      const cell = tr.insertCell();
      cell.textContent = String(row[field.name]);
    });
  });
}

function createFileObj(file_package) {
  if (file_package && file_package.file_content && file_package.file_info) {
    const { file_content, file_info } = file_package;

    const byteCharacters = atob(file_content);
    const byteNumbers = new Array(byteCharacters.length);
    for (let i = 0; i < byteCharacters.length; i++) {
      byteNumbers[i] = byteCharacters.charCodeAt(i);
    }
    const byteArray = new Uint8Array(byteNumbers);

    const blob = new Blob([byteArray], { type: file_info.type });

    const file = new File([blob], file_info.name, {
      type: file_info.type,
      lastModified: file_info.lastModified,
    });

    return file;
  }
  return null;
}

function render({ model, el }) {
  const idb = model.get("idb");
  const file_data = model.get("file_package");
  const data = createFileObj(file_data);
  const options = {};
  if (data) options.loadDataDir = data;

  //const db = new PGlite();
  const db = idb ? new PGlite(idb, options) : new PGlite(options);
  const _headless = model.get("headless");

  let el2 = document.createElement("div");
  el2.innerHTML = html;
  const uuid = generateUUID();
  el2.id = uuid;

  if (_headless) {
    el2.style = "display: none; visibility: hidden;";
  }

  el.appendChild(el2);

  model.on("change:datadump", async () => {
    const datadump = model.get("datadump");
    if (datadump == "generate_dump") {
      let dumpfile = await db.dumpDataDir();
      const reader = new FileReader();
      reader.onload = (e) => {
        const file_info = {
          name: dumpfile.name,
          size: dumpfile.size,
          type: dumpfile.type,
          lastModified: dumpfile.lastModified,
        };

        const file_content = e.target.result.split(",")[1];

        const file_package = {
          file_info: file_info,
          file_content: file_content,
        };

        model.set("file_package", file_package);
        model.set("response", { status: "datadump_ready" });
        model.save_changes();
        if (model.get("audio")) play_success();
      };
      reader.readAsDataURL(dumpfile);
    }
  });

  model.on("change:code_content", async () => {
    function queryDisplay(q) {
      if (_headless) return;

      const codeEditor = el.querySelector('div[title="code-editor"]');
      codeEditor.innerHTML = codeEditor.innerHTML + "<br>" + q;
    }

    function resultDisplay(response) {
      if (_headless) return;

      const output = el.querySelector('div[title="output"]');
      const results = el.querySelector('div[title="results"]');

      output.innerHTML = JSON.stringify(response);
      const table = formatTable(response);
      formatRows(response, table);
      results.innerHTML = "";
      results.append(table);
    }

    function fullDisplay(q, r) {
      if (_headless) return;

      queryDisplay(q);
      resultDisplay(r);
    }

    function handle_error(error) {
      if (model.get("audio")) play_error(error.message);
      model.set("response", {
        status: "error",
        error_message: error.message,
      });
    }

    const sql = model.get("code_content");
    if (!sql) return;

    const multiline = model.get("multiline");
    const multiexec = model.get("multiexec");
    let response = {
      rows: [],
      fields: [{ name: "", dataTypeID: 0 }],
    };

    if (multiexec) {
      try {
        queryDisplay(sql);
        let multi_response = await db.exec(sql);
        resultDisplay(multi_response[multi_response.length - 1]);
        model.set("response", {
          status: "completed",
          response: multi_response,
          response_type: "multi",
        });
      } catch (error) {
        handle_error(error);
      }
    } else if (multiline != "") {
      const items = sql.split(multiline);

      for (const item of items) {
        const q = item.trim();
        if (q !== "") {
          queryDisplay(`${q};`);
          try {
            response = await db.query(q);
            resultDisplay(response);
          } catch (error) {
            handle_error(error);
          }
        }
      }
      model.set("response", {
        status: "completed",
        response: response,
        response_type: "single",
      });
    } else {
      queryDisplay(sql);
      try {
        if (model.get("describe"))
            response= await db.describeQuery(sql)
        else {
            response = await db.query(sql);
            resultDisplay(response);
        }
        model.set("response", {
          status: "completed",
          response: response,
          response_type: "single",
        });
      } catch (error) {
        handle_error(error);
      }
    }

    model.save_changes();
    if (model.get("audio")) play_success();
  });

  let db_version;
  db.query("select version();")
    .then((result) => {
      db_version = result["rows"][0]; // Assign the result to the outer variable
      //console.log("DB Version:", db_version);
      model.set("about", db_version);
      model.set("response", { status: "ready" });
      model.save_changes();
    })
    .catch((err) => {
      alert(err);
      console.error("Error executing query:", err);
    });

    return () => {
        // Safe clean up of the database
        db.close()
    }
}

export default { render };
