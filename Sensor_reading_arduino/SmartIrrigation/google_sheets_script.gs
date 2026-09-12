// Smart Irrigation → Google Sheet you can see
//
// CREATE THE SHEET FIRST (this is how you get the link):
// 1. Open https://sheets.new
// 2. Rename the file: Tomato Greenhouse Irrigation
// 3. Extensions → Apps Script
// 4. Delete the default code, paste THIS entire file, Save
// 5. Select setupSheet → Run → Allow
// 6. Go back to the spreadsheet tab — headers are in row 1
// 7. Deploy → New deployment → Web app
//    Execute as: Me
//    Who has access: Anyone
// 8. Copy the /exec URL into SCRIPT_URL in SmartIrrigation.ino
//
// To see the spreadsheet URL later: select showSheetUrl → Run
// View → Execution log
//
// Opening the /exec URL in a browser (no extra parameters) also prints the sheet link.
// Do not click Run on doGet. The ESP32 writes the sensor rows.

var HEADERS = [
  "Timestamp",
  "Crop",
  "Temperature (C)",
  "Humidity (%)",
  "Pressure (hPa)",
  "Soil Moisture (%)",
  "Relay (1=ON 0=OFF)",
  "Water needed (ML)",
  "Temp Min",
  "Temp Max",
  "Humidity Min",
  "Humidity Max",
  "Soil Min",
  "Soil Max",
  "Temp Status",
  "Humidity Status",
  "Soil Status",
  "Device ID"
];

function setupSheet() {
  var ss = getSpreadsheet_();
  var sheet = getSensorTab_(ss);
  sheet.clear();
  writeHeaders_(sheet);
  sheet.appendRow([
    new Date(),
    "tomato",
    24.5,
    68,
    865,
    52,
    1,
    1,
    18, 30, 60, 80, 40, 70,
    "OK", "OK", "OK",
    "setup-test"
  ]);
  PropertiesService.getScriptProperties().setProperty("SPREADSHEET_ID", ss.getId());
  Logger.log("SHEET URL: " + ss.getUrl());
  return ss.getUrl();
}

function showSheetUrl() {
  var ss = getSpreadsheet_();
  Logger.log("SHEET URL: " + ss.getUrl());
  return ss.getUrl();
}

function doGet(e) {
  var data = collectParams_(e);
  if (hasSensorData_(data)) {
    writeSensorRow(data);
    return ContentService.createTextOutput("OK: Row added");
  }

  var ss = getSpreadsheet_();
  return ContentService.createTextOutput("Spreadsheet URL: " + ss.getUrl());
}

function doPost(e) {
  var data = {};

  if (e && e.postData && e.postData.contents) {
    try {
      data = JSON.parse(e.postData.contents);
    } catch (err) {
      data = (e && e.parameter) ? e.parameter : {};
    }
  } else {
    data = (e && e.parameter) ? e.parameter : {};
  }

  if (!hasSensorData_(data)) {
    var ss = getSpreadsheet_();
    return ContentService.createTextOutput("Spreadsheet URL: " + ss.getUrl());
  }

  writeSensorRow(data);
  return ContentService.createTextOutput("OK: Row added");
}

function collectParams_(e) {
  if (e && e.parameter) {
    return e.parameter;
  }
  return {};
}

function hasSensorData_(data) {
  return data && (
    data.temperature !== undefined ||
    data.humidity !== undefined ||
    data.soilMoisture !== undefined ||
    data.relay !== undefined
  );
}

function writeSensorRow(data) {
  var sheet = getTargetSheet();
  writeHeaders_(sheet);

  var t = num_(data.temperature);
  var h = num_(data.humidity);
  var p = num_(data.pressure, 865);
  var s = num_(data.soilMoisture);
  var relay = toBinaryRelay_(data.relay);

  var tMin = num_(data.temp_min, 18);
  var tMax = num_(data.temp_max, 30);
  var hMin = num_(data.hum_min, 60);
  var hMax = num_(data.hum_max, 80);
  var sMin = num_(data.soil_min, 40);
  var sMax = num_(data.soil_max, 70);

  var row = findNextRow_(sheet);
  sheet.getRange(row, 1, 1, HEADERS.length).setValues([[
    new Date(),
    data.crop || "tomato",
    t,
    h,
    p,
    s,
    relay,
    toBinaryRelay_(data.water_needed !== undefined ? data.water_needed : relay),
    tMin,
    tMax,
    hMin,
    hMax,
    sMin,
    sMax,
    data.temp_status || status_(t, tMin, tMax),
    data.hum_status || status_(h, hMin, hMax),
    data.soil_status || status_(s, sMin, sMax),
    data.device_id || ""
  ]]);
}

function toBinaryRelay_(value) {
  var n = parseInt(value, 10);
  if (n === 1 || String(value).toLowerCase() === "on") {
    return 1;
  }
  return 0;
}

function status_(value, minV, maxV) {
  if (value === "" || value === null || isNaN(value)) {
    return "";
  }
  if (value < minV) {
    return "LOW";
  }
  if (value > maxV) {
    return "HIGH";
  }
  return "OK";
}

function num_(value, fallback) {
  if (value === undefined || value === null || value === "") {
    return (fallback !== undefined) ? fallback : "";
  }
  var n = parseFloat(value);
  return isNaN(n) ? ((fallback !== undefined) ? fallback : "") : n;
}

function writeHeaders_(sheet) {
  sheet.getRange(1, 1, 1, HEADERS.length).setValues([HEADERS]);
  sheet.getRange(1, 1, 1, HEADERS.length).setFontWeight("bold");
}

function findNextRow_(sheet) {
  var last = sheet.getLastRow();
  if (last < 1) {
    writeHeaders_(sheet);
    return 2;
  }

  var scan = Math.max(last, 2);
  var values = sheet.getRange(1, 1, scan, 1).getValues();
  var lastData = 1;
  for (var i = 1; i < values.length; i++) {
    if (String(values[i][0]).trim() !== "") {
      lastData = i + 1;
    }
  }
  return lastData + 1;
}

function getTargetSheet() {
  return getSensorTab_(getSpreadsheet_());
}

function getSensorTab_(ss) {
  var sheet = ss.getSheetByName("SensorData");
  if (sheet) {
    return sheet;
  }
  sheet = ss.getSheets()[0];
  sheet.setName("SensorData");
  return sheet;
}

function getSpreadsheet_() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  if (ss) {
    PropertiesService.getScriptProperties().setProperty("SPREADSHEET_ID", ss.getId());
    return ss;
  }

  var id = PropertiesService.getScriptProperties().getProperty("SPREADSHEET_ID");
  if (id) {
    return SpreadsheetApp.openById(id);
  }

  throw new Error(
    "No spreadsheet found. Open https://sheets.new then Extensions → Apps Script and paste this code there. Run setupSheet."
  );
}
