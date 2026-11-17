/**
 * BusinessBrain invitation email relay.
 *
 * Deploy as a Web app:
 * - Execute as: Me
 * - Who has access: Anyone
 * Then set BB_RELAY_SECRET in Project Settings > Script properties.
 * The shared secret is required for every request; never publish it.
 */
function doPost(e) {
  try {
    var input = JSON.parse((e && e.postData && e.postData.contents) || "{}");
    var expected = PropertiesService.getScriptProperties().getProperty("BB_RELAY_SECRET");
    if (!expected || !input.secret || input.secret !== expected) {
      return json_({ ok: false, error: "unauthorized" });
    }
    var to = String(input.to || "").trim();
    var subject = String(input.subject || "").trim();
    var body = String(input.text || "");
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(to) ||
        !subject || subject.length > 200 || !body || body.length > 12000) {
      return json_({ ok: false, error: "invalid_request" });
    }
    if (MailApp.getRemainingDailyQuota() < 1) {
      return json_({ ok: false, error: "daily_quota_exceeded" });
    }
    MailApp.sendEmail({ to: to, subject: subject, body: body, name: "BusinessBrain" });
    return json_({ ok: true });
  } catch (err) {
    console.error("BusinessBrain mail relay failed: " + String(err));
    return json_({ ok: false, error: "send_failed" });
  }
}

function json_(value) {
  return ContentService.createTextOutput(JSON.stringify(value))
    .setMimeType(ContentService.MimeType.JSON);
}
