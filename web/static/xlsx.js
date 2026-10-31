// Writes a small Excel file in the browser, so typed names never leave the
// device. An .xlsx is a zip of XML files: it has no encoding or separator to
// guess, unlike a CSV, and text cells are never run as formulas.
"use strict";

const CRC_TABLE = Array.from({length: 256}, (_, index) => {
  let value = index;
  for (let bit = 0; bit < 8; bit++) value = value & 1 ? 0xedb88320 ^ (value >>> 1) : value >>> 1;
  return value >>> 0;
});

function crc32(bytes) {
  let crc = 0xffffffff;
  for (const byte of bytes) crc = CRC_TABLE[(crc ^ byte) & 0xff] ^ (crc >>> 8);
  return (crc ^ 0xffffffff) >>> 0;
}

function littleEndian(...fields) {
  // Each field is [value, size in bytes]
  const bytes = [];
  for (const [value, size] of fields) {
    for (let index = 0; index < size; index++) bytes.push(Math.floor(value / 256 ** index) & 0xff);
  }
  return new Uint8Array(bytes);
}

// A zip without compression: the files are small
function zip(files) {
  const encoder = new TextEncoder();
  const DATE = 0x0021; // 1 January 1980, the first valid zip date
  const parts = [];
  const directory = [];
  let offset = 0;
  for (const [name, text] of Object.entries(files)) {
    const nameBytes = encoder.encode(name);
    const data = encoder.encode(text);
    const shared = [[20, 2], [0x0800, 2], [0, 2], [0, 2], [DATE, 2], [crc32(data), 4],
                    [data.length, 4], [data.length, 4], [nameBytes.length, 2], [0, 2]];
    const header = littleEndian([0x04034b50, 4], ...shared);
    parts.push(header, nameBytes, data);
    directory.push(littleEndian([0x02014b50, 4], [20, 2], ...shared, [0, 2], [0, 2], [0, 2],
                                [0, 4], [offset, 4]), nameBytes);
    offset += header.length + nameBytes.length + data.length;
  }
  const size = directory.reduce((total, part) => total + part.length, 0);
  const count = Object.keys(files).length;
  const end = littleEndian([0x06054b50, 4], [0, 2], [0, 2], [count, 2], [count, 2],
                           [size, 4], [offset, 4], [0, 2]);
  return new Blob([...parts, ...directory, end]);
}

function escapeXml(text) {
  return String(text)
    .replace(/[^\t\n\r -퟿-�]/gu, "")
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function columnName(index) {
  return String.fromCharCode(65 + index);
}

function cell(value, column, row) {
  const place = `${columnName(column)}${row}`;
  if (value === null || value === undefined || value === "") return "";
  if (typeof value === "number") return `<c r="${place}"><v>${value}</v></c>`;
  return `<c r="${place}" t="inlineStr"><is><t xml:space="preserve">${escapeXml(value)}</t></is></c>`;
}

// rows is a list of lists of texts and numbers. widths has one number per column
function makeXlsx(rows, widths) {
  const XML = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n';
  const MAIN = "http://schemas.openxmlformats.org/spreadsheetml/2006/main";
  const RELS = "http://schemas.openxmlformats.org/package/2006/relationships";
  const OFFICE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships";
  const columns = widths.map((width, index) =>
    `<col min="${index + 1}" max="${index + 1}" width="${width}" customWidth="1"/>`).join("");
  const sheetRows = rows.map((row, index) =>
    `<row r="${index + 1}">${row.map((value, column) => cell(value, column, index + 1)).join("")}</row>`).join("");
  return zip({
    "[Content_Types].xml": `${XML}<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">`
      + '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
      + '<Default Extension="xml" ContentType="application/xml"/>'
      + '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
      + '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
      + "</Types>",
    "_rels/.rels": `${XML}<Relationships xmlns="${RELS}"><Relationship Id="rId1" `
      + `Type="${OFFICE}/officeDocument" Target="xl/workbook.xml"/></Relationships>`,
    "xl/workbook.xml": `${XML}<workbook xmlns="${MAIN}" xmlns:r="${OFFICE}"><sheets>`
      + '<sheet name="Equipos" sheetId="1" r:id="rId1"/></sheets></workbook>',
    "xl/_rels/workbook.xml.rels": `${XML}<Relationships xmlns="${RELS}"><Relationship Id="rId1" `
      + `Type="${OFFICE}/worksheet" Target="worksheets/sheet1.xml"/></Relationships>`,
    "xl/worksheets/sheet1.xml": `${XML}<worksheet xmlns="${MAIN}"><cols>${columns}</cols>`
      + `<sheetData>${sheetRows}</sheetData></worksheet>`,
  });
}
