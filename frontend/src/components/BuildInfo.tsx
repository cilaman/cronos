import { useBuildInfo } from "../hooks/useBuildInfo";

const BUILD_TIME_DIVERGENCE_MS = 5 * 60 * 1000;

function formatUtc(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (isNaN(d.getTime())) return iso;
  const pad = (n: number) => String(n).padStart(2, "0");
  return (
    `${d.getUTCFullYear()}-${pad(d.getUTCMonth() + 1)}-${pad(d.getUTCDate())} ` +
    `${pad(d.getUTCHours())}:${pad(d.getUTCMinutes())} UTC`
  );
}

function timesAreDiverged(a: string | null | undefined, b: string | null | undefined): boolean {
  if (!a || !b) return false;
  const ta = new Date(a).getTime();
  const tb = new Date(b).getTime();
  if (isNaN(ta) || isNaN(tb)) return false;
  return Math.abs(ta - tb) > BUILD_TIME_DIVERGENCE_MS;
}

export function BuildInfo() {
  const { data } = useBuildInfo();

  const backendSha = data?.commit_sha ?? null;
  const backendTime = data?.build_time ?? null;
  const repoUrl = data?.repo_url ?? null;

  const frontendTime: string | null = import.meta.env.VITE_BUILD_TIME || null;

  const shortSha = backendSha ? backendSha.slice(0, 7) : null;

  const showTwoTimestamps = timesAreDiverged(backendTime, frontendTime);
  const displayTime = backendTime ?? frontendTime;

  return (
    <div
      className="font-mono text-[9px] leading-snug tracking-[0.08em] text-ink-faint"
      style={{ minHeight: "2.4em" }}
    >
      {shortSha && (
        <div>
          {shortSha && repoUrl ? (
            <a
              href={`${repoUrl}/commit/${backendSha}`}
              target="_blank"
              rel="noopener noreferrer"
              className="text-ink-faint hover:text-accent-bright transition"
            >
              {shortSha}
            </a>
          ) : (
            <span>{shortSha}</span>
          )}
        </div>
      )}
      {showTwoTimestamps ? (
        <>
          <div>API: {formatUtc(backendTime)}</div>
          <div>UI: {formatUtc(frontendTime)}</div>
        </>
      ) : displayTime ? (
        <div>Built {formatUtc(displayTime)}</div>
      ) : null}
    </div>
  );
}
