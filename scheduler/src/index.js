// Starts the intraday run of .github/workflows/daily.yml on time. See ADR 0006.
//
// GitHub Actions cron was observed firing the 15:25 ET intraday schedule 3.5-4.5
// hours late, every day, so the run always landed after the close and skipped.
// Cloudflare cron fires on time; this Worker turns it into a workflow_dispatch.
//
// Both crons are UTC and only one of them is 15:30 ET on any given day (the DST
// pair, same as ADR 0005). The wrong one is dropped HERE rather than dispatched
// and skipped by the workflow, so the Actions history holds one intraday run a
// day. Holidays are still caught downstream by quote.provisional().

const REPO = "imtaehyun/tripod-signal";
const WORKFLOW = "daily.yml";
const DISPATCH_HOUR_ET = 15;

export function hourET(date) {
  const h = new Intl.DateTimeFormat("en-US", {
    timeZone: "America/New_York", hour: "numeric", hourCycle: "h23",
  }).format(date);
  return Number(h);
}

async function dispatch(env) {
  const res = await fetch(
    `https://api.github.com/repos/${REPO}/actions/workflows/${WORKFLOW}/dispatches`,
    {
      method: "POST",
      headers: {
        Accept: "application/vnd.github+json",
        Authorization: `Bearer ${env.GITHUB_TOKEN}`,
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "tripod-signal-scheduler",
      },
      body: JSON.stringify({ ref: "main", inputs: { mode: "intraday" } }),
    },
  );
  if (!res.ok) throw new Error(`GitHub ${res.status}: ${await res.text()}`);
}

// The workflow's own failure message cannot fire if the workflow never starts,
// so a failed dispatch has to be loud from here. Same rule as notify.py: a
// silent failure and a quiet day are indistinguishable.
async function alert(env, text) {
  if (!env.TELEGRAM_BOT_TOKEN || !env.TELEGRAM_CHAT_ID) return;
  await fetch(`https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/sendMessage`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ chat_id: env.TELEGRAM_CHAT_ID, text }),
  });
}

export default {
  async scheduled(controller, env) {
    const at = new Date(controller.scheduledTime);
    if (hourET(at) !== DISPATCH_HOUR_ET) {
      console.log(`${controller.cron}: wrong half of the DST pair, skipping`);
      return;
    }
    // Three tries inside a minute. The run sleeps to 15:45 ET, so there are
    // ~15 minutes of slack; a retry costs nothing and a missed day costs a fill.
    let last;
    for (let i = 0; i < 3; i++) {
      try {
        await dispatch(env);
        console.log("dispatched intraday run");
        return;
      } catch (err) {
        last = err;
        console.error(`dispatch attempt ${i + 1} failed: ${err.message}`);
        await new Promise((r) => setTimeout(r, 15_000));
      }
    }
    await alert(env, `🚨 장중 판정 실행 실패: GitHub workflow를 시작하지 못했다.\n${last.message}`);
    throw last;
  },
};
