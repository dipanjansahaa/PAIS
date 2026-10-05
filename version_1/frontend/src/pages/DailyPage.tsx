import { useEffect, useState } from "react";

import {
  ApiError,
  getDaily,
  type DailyResponse,
} from "../lib/api";
import EmptyState from "../components/feedback/EmptyState";
import ErrorState from "../components/feedback/ErrorState";
import LoadingState from "../components/feedback/LoadingState";

function getTodayDate(): string {
  return new Intl.DateTimeFormat("en-CA").format(new Date());
}

function getLocalTimezone(): string {
  const timezone = Intl.DateTimeFormat().resolvedOptions().timeZone;

  const timezoneAliases: Record<string, string> = {
    "Asia/Calcutta": "Asia/Kolkata",
  };

  return timezoneAliases[timezone] ?? timezone;
}

function formatDailyDate(day: string, timezoneName: string): string {
  const date = new Date(`${day}T00:00:00`);

  return new Intl.DateTimeFormat("en-US", {
    dateStyle: "long",
    timeZone: timezoneName,
  }).format(date);
}

function DailyPage() {
  const [daily, setDaily] = useState<DailyResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  async function loadDaily(signal?: AbortSignal) {
    setIsLoading(true);
    setErrorMessage(null);

    try {
      const result = await getDaily(
        {
          day: getTodayDate(),
          timezone_name: getLocalTimezone(),
        },
        signal,
      );

      if (!signal?.aborted) {
        setDaily(result);
      }
    } catch (error) {
      if (
        signal?.aborted ||
        (error instanceof DOMException && error.name === "AbortError")
      ) {
        return;
      }

      if (error instanceof ApiError) {
        setErrorMessage(error.message);
      } else if (error instanceof Error) {
        setErrorMessage(error.message);
      } else {
        setErrorMessage("Unable to load daily intelligence.");
      }
    } finally {
      if (!signal?.aborted) {
        setIsLoading(false);
      }
    }
  }

  useEffect(() => {
    const controller = new AbortController();

    void loadDaily(controller.signal);

    return () => {
      controller.abort();
    };
  }, []);

  if (isLoading) {
    return (
      <section className="page daily-page">
        <div className="page-header">
          <p className="page-eyebrow">DAILY INTELLIGENCE</p>
          <h2>Daily</h2>
          <p className="page-description">
            Your daily intelligence brief, priorities, decisions, changes,
            and risks.
          </p>
        </div>

        <LoadingState message="Generating daily intelligence..." />
      </section>
    );
  }

  if (errorMessage) {
    return (
      <section className="page daily-page">
        <div className="page-header">
          <p className="page-eyebrow">DAILY INTELLIGENCE</p>
          <h2>Daily</h2>
          <p className="page-description">
            Your daily intelligence brief, priorities, decisions, changes,
            and risks.
          </p>
        </div>

        <ErrorState
          title="Daily intelligence failed"
          message={errorMessage}
          onRetry={() => {
            void loadDaily();
          }}
        />
      </section>
    );
  }

  if (!daily) {
    return (
      <section className="page daily-page">
        <div className="page-header">
          <p className="page-eyebrow">DAILY INTELLIGENCE</p>
          <h2>Daily</h2>
          <p className="page-description">
            Your daily intelligence brief, priorities, decisions, changes,
            and risks.
          </p>
        </div>

        <EmptyState
          title="No daily intelligence"
          message="No daily intelligence was returned."
        />
      </section>
    );
  }

  return (
    <section className="page daily-page">
      <div className="page-header">
        <p className="page-eyebrow">DAILY INTELLIGENCE</p>

        <h2>Daily</h2>

        <p className="page-description">
          Your daily intelligence brief, priorities, decisions, changes,
          and risks.
        </p>

        <div className="daily-meta">
          <span>
            {formatDailyDate(daily.day, daily.timezone_name)}
          </span>

          <span>{daily.timezone_name}</span>
        </div>
      </div>

      <div className="daily-layout">
        <section className="daily-card daily-summary-card">
          <div className="section-header">
            <div>
              <h3>Summary</h3>
              <p>
                A concise overview of your current daily intelligence.
              </p>
            </div>
          </div>

          <p className="daily-summary">
            {daily.summary}
          </p>
        </section>

        <div className="daily-grid">
          <section className="daily-card daily-priorities-card">
            <div className="section-header">
              <div>
                <h3>Priorities</h3>
                <p>
                  Items ranked by the deterministic priority engine.
                </p>
              </div>
            </div>

            {daily.priorities.length > 0 ? (
              <ul className="daily-list">
                {daily.priorities.map((priority, index) => (
                  <li key={`${priority}-${index}`}>
                    {priority}
                  </li>
                ))}
              </ul>
            ) : (
              <EmptyState
                title="No priorities"
                message="No priority items were identified for this day."
              />
            )}
          </section>

          <section className="daily-card daily-decisions-card">
            <div className="section-header">
              <div>
                <h3>Decisions</h3>
                <p>
                  Recent decisions relevant to the daily context.
                </p>
              </div>
            </div>

            {daily.decisions.length > 0 ? (
              <ul className="daily-list">
                {daily.decisions.map((decision, index) => (
                  <li key={`${decision}-${index}`}>
                    {decision}
                  </li>
                ))}
              </ul>
            ) : (
              <EmptyState
                title="No recent decisions"
                message="No recent decisions were identified for this day."
              />
            )}
          </section>

          <section className="daily-card daily-changes-card">
            <div className="section-header">
              <div>
                <h3>Changes</h3>
                <p>
                  Recent changes detected in your intelligence context.
                </p>
              </div>
            </div>

            {daily.changes.length > 0 ? (
              <ul className="daily-list">
                {daily.changes.map((change, index) => (
                  <li key={`${change}-${index}`}>
                    {change}
                  </li>
                ))}
              </ul>
            ) : (
              <EmptyState
                title="No recent changes"
                message="No recent changes were identified for this day."
              />
            )}
          </section>

          <section className="daily-card daily-risks-card">
            <div className="section-header">
              <div>
                <h3>Risks</h3>
                <p>
                  Risks identified in the daily intelligence context.
                </p>
              </div>
            </div>

            {daily.risks.length > 0 ? (
              <ul className="daily-list">
                {daily.risks.map((risk, index) => (
                  <li key={`${risk}-${index}`}>
                    {risk}
                  </li>
                ))}
              </ul>
            ) : (
              <EmptyState
                title="No risks"
                message="No risks were identified for this day."
              />
            )}
          </section>
        </div>

        <div className="daily-generation-meta">
          <span>
            Model: {daily.model ?? "Deterministic"}
          </span>

          {daily.latency_ms !== null && (
            <span>
              Latency: {daily.latency_ms} ms
            </span>
          )}
        </div>
      </div>
    </section>
  );
}

export default DailyPage;