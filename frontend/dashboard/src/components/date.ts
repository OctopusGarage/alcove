const SINGAPORE_TIME_ZONE = "Asia/Singapore";

export function formatSingaporeDateTime(
  value: unknown,
  options: { seconds?: boolean } = {},
): string {
  const raw = String(value ?? "").trim();
  if (!raw) {
    return "No timestamp";
  }
  if (/^\d{4}-\d{2}-\d{2}$/.test(raw)) {
    return formatDateOnly(raw);
  }
  const date = new Date(raw);
  if (Number.isNaN(date.getTime())) {
    return raw;
  }
  const parts = new Intl.DateTimeFormat("en-SG", {
    timeZone: SINGAPORE_TIME_ZONE,
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    second: options.seconds ? "2-digit" : undefined,
    hour12: false,
  }).formatToParts(date);
  const part = (type: Intl.DateTimeFormatPartTypes): string =>
    parts.find((item) => item.type === type)?.value ?? "";
  const time = options.seconds
    ? `${part("hour")}:${part("minute")}:${part("second")}`
    : `${part("hour")}:${part("minute")}`;
  return `${part("month")} ${Number(part("day"))}, ${part("year")}, ${time} SGT`;
}

function formatDateOnly(raw: string): string {
  const [year, month, day] = raw.split("-");
  const date = new Date(`${raw}T00:00:00+08:00`);
  if (Number.isNaN(date.getTime())) {
    return raw;
  }
  return new Intl.DateTimeFormat("en-SG", {
    timeZone: SINGAPORE_TIME_ZONE,
    year: "numeric",
    month: "short",
    day: "numeric",
  }).format(date);
}
