import { useEffect, useState } from "react";

import {
  ApiError,
  getIntelligence,
  type IntelligenceResponse,
} from "../lib/api";
import EmptyState from "../components/feedback/EmptyState";
import ErrorState from "../components/feedback/ErrorState";
import LoadingState from "../components/feedback/LoadingState";

function formatDate(value: string | null): string {
  if (!value) {
    return "—";
  }

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return new Intl.DateTimeFormat("en-US", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

function formatStatus(value: string): string {
  return value.replaceAll("_", " ");
}

function IntelligencePage() {
  const [intelligence, setIntelligence] =
    useState<IntelligenceResponse | null>(null);

  const [isLoading, setIsLoading] = useState(true);
  const [errorMessage, setErrorMessage] =
    useState<string | null>(null);

  async function loadIntelligence(signal?: AbortSignal) {
    setIsLoading(true);
    setErrorMessage(null);

    try {
      const result = await getIntelligence(signal);

      setIntelligence(result);
    } catch (error) {
      if (signal?.aborted) {
        return;
      }

      if (error instanceof ApiError) {
        setErrorMessage(error.message);
      } else if (error instanceof Error) {
        setErrorMessage(error.message);
      } else {
        setErrorMessage(
          "Unable to load structured intelligence.",
        );
      }
    } finally {
      if (!signal?.aborted) {
        setIsLoading(false);
      }
    }
  }

  useEffect(() => {
    const controller = new AbortController();

    void loadIntelligence(controller.signal);

    return () => {
      controller.abort();
    };
  }, []);

  if (isLoading) {
    return (
      <section className="page intelligence-page">
        <div className="page-header">
          <p className="page-eyebrow">
            STRUCTURED INTELLIGENCE
          </p>

          <h2>Intelligence</h2>

          <p className="page-description">
            Persisted tasks, commitments, decisions, projects,
            people, and risks extracted from your source material.
          </p>
        </div>

        <LoadingState message="Loading structured intelligence..." />
      </section>
    );
  }

  if (errorMessage) {
    return (
      <section className="page intelligence-page">
        <div className="page-header">
          <p className="page-eyebrow">
            STRUCTURED INTELLIGENCE
          </p>

          <h2>Intelligence</h2>

          <p className="page-description">
            Persisted tasks, commitments, decisions, projects,
            people, and risks extracted from your source material.
          </p>
        </div>

        <ErrorState
          title="Intelligence failed"
          message={errorMessage}
          onRetry={() => {
            void loadIntelligence();
          }}
        />
      </section>
    );
  }

  if (!intelligence) {
    return (
      <section className="page intelligence-page">
        <div className="page-header">
          <p className="page-eyebrow">
            STRUCTURED INTELLIGENCE
          </p>

          <h2>Intelligence</h2>
        </div>

        <EmptyState
          title="No intelligence"
          message="No structured intelligence was returned."
        />
      </section>
    );
  }

  const hasIntelligence =
    intelligence.tasks.length > 0 ||
    intelligence.commitments.length > 0 ||
    intelligence.decisions.length > 0 ||
    intelligence.projects.length > 0 ||
    intelligence.people.length > 0 ||
    intelligence.risks.length > 0;

  return (
    <section className="page intelligence-page">
      <div className="page-header">
        <p className="page-eyebrow">
          STRUCTURED INTELLIGENCE
        </p>

        <h2>Intelligence</h2>

        <p className="page-description">
          Persisted structured information extracted from your
          source material, with provenance preserved back to
          document chunks.
        </p>
      </div>

      {!hasIntelligence ? (
        <EmptyState
          title="No structured intelligence yet"
          message="Upload and process source material to populate this view."
        />
      ) : (
        <div className="intelligence-grid">
          <section className="intelligence-card">
            <div className="section-header">
              <div>
                <h3>Tasks</h3>
                <p>
                  Work items that need to be completed.
                </p>
              </div>

              <span className="intelligence-count">
                {intelligence.tasks.length}
              </span>
            </div>

            {intelligence.tasks.length > 0 ? (
              <div className="intelligence-list">
                {intelligence.tasks.map((task) => (
                  <article
                    className="intelligence-item"
                    key={task.id}
                  >
                    <div className="intelligence-item-header">
                      <h4>{task.description}</h4>

                      <span className="intelligence-status">
                        {formatStatus(task.status)}
                      </span>
                    </div>

                    <div className="intelligence-item-meta">
                      {task.owner && (
                        <span>
                          Owner: {task.owner}
                        </span>
                      )}

                      {task.priority && (
                        <span>
                          Priority: {task.priority}
                        </span>
                      )}

                      {task.due_at && (
                        <span>
                          Due: {formatDate(task.due_at)}
                        </span>
                      )}
                    </div>

                    <div className="intelligence-sources">
                      <span>Sources</span>

                      <span>
                        {task.source_chunk_ids.length}
                      </span>
                    </div>
                  </article>
                ))}
              </div>
            ) : (
              <EmptyState
                title="No tasks"
                message="No tasks are currently stored."
              />
            )}
          </section>

          <section className="intelligence-card">
            <div className="section-header">
              <div>
                <h3>Commitments</h3>
                <p>
                  Obligations and promises that need tracking.
                </p>
              </div>

              <span className="intelligence-count">
                {intelligence.commitments.length}
              </span>
            </div>

            {intelligence.commitments.length > 0 ? (
              <div className="intelligence-list">
                {intelligence.commitments.map((commitment) => (
                  <article
                    className="intelligence-item"
                    key={commitment.id}
                  >
                    <div className="intelligence-item-header">
                      <h4>{commitment.description}</h4>

                      <span className="intelligence-status">
                        {formatStatus(commitment.status)}
                      </span>
                    </div>

                    <div className="intelligence-item-meta">
                      {commitment.owner && (
                        <span>
                          Owner: {commitment.owner}
                        </span>
                      )}

                      {commitment.deadline_at && (
                        <span>
                          Deadline:{" "}
                          {formatDate(commitment.deadline_at)}
                        </span>
                      )}
                    </div>

                    <div className="intelligence-sources">
                      <span>Sources</span>

                      <span>
                        {commitment.source_chunk_ids.length}
                      </span>
                    </div>
                  </article>
                ))}
              </div>
            ) : (
              <EmptyState
                title="No commitments"
                message="No commitments are currently stored."
              />
            )}
          </section>

          <section className="intelligence-card">
            <div className="section-header">
              <div>
                <h3>Decisions</h3>
                <p>
                  Decisions preserved with their provenance.
                </p>
              </div>

              <span className="intelligence-count">
                {intelligence.decisions.length}
              </span>
            </div>

            {intelligence.decisions.length > 0 ? (
              <div className="intelligence-list">
                {intelligence.decisions.map((decision) => (
                  <article
                    className="intelligence-item"
                    key={decision.id}
                  >
                    <div className="intelligence-item-header">
                      <h4>{decision.title}</h4>

                      <span className="intelligence-status">
                        {formatStatus(decision.status)}
                      </span>
                    </div>

                    <p className="intelligence-item-description">
                      {decision.description}
                    </p>

                    {decision.decision_date && (
                      <div className="intelligence-item-meta">
                        <span>
                          Date:{" "}
                          {formatDate(
                            decision.decision_date,
                          )}
                        </span>
                      </div>
                    )}

                    <div className="intelligence-sources">
                      <span>Sources</span>

                      <span>
                        {decision.source_chunk_ids.length}
                      </span>
                    </div>
                  </article>
                ))}
              </div>
            ) : (
              <EmptyState
                title="No decisions"
                message="No decisions are currently stored."
              />
            )}
          </section>

          <section className="intelligence-card">
            <div className="section-header">
              <div>
                <h3>Projects</h3>
                <p>
                  Longer-running areas of work.
                </p>
              </div>

              <span className="intelligence-count">
                {intelligence.projects.length}
              </span>
            </div>

            {intelligence.projects.length > 0 ? (
              <div className="intelligence-list">
                {intelligence.projects.map((project) => (
                  <article
                    className="intelligence-item"
                    key={project.id}
                  >
                    <div className="intelligence-item-header">
                      <h4>{project.name}</h4>

                      <span className="intelligence-status">
                        {formatStatus(project.status)}
                      </span>
                    </div>

                    {project.description && (
                      <p className="intelligence-item-description">
                        {project.description}
                      </p>
                    )}

                    <div className="intelligence-sources">
                      <span>Sources</span>

                      <span>
                        {project.source_chunk_ids.length}
                      </span>
                    </div>
                  </article>
                ))}
              </div>
            ) : (
              <EmptyState
                title="No projects"
                message="No projects are currently stored."
              />
            )}
          </section>

          <section className="intelligence-card">
            <div className="section-header">
              <div>
                <h3>People</h3>
                <p>
                  People identified in your source material.
                </p>
              </div>

              <span className="intelligence-count">
                {intelligence.people.length}
              </span>
            </div>

            {intelligence.people.length > 0 ? (
              <div className="intelligence-list">
                {intelligence.people.map((person) => (
                  <article
                    className="intelligence-item"
                    key={person.id}
                  >
                    <div className="intelligence-item-header">
                      <h4>{person.name}</h4>
                    </div>

                    {person.email && (
                      <p className="intelligence-item-description">
                        {person.email}
                      </p>
                    )}

                    <div className="intelligence-sources">
                      <span>Sources</span>

                      <span>
                        {person.source_chunk_ids.length}
                      </span>
                    </div>
                  </article>
                ))}
              </div>
            ) : (
              <EmptyState
                title="No people"
                message="No people are currently stored."
              />
            )}
          </section>

          <section className="intelligence-card">
            <div className="section-header">
              <div>
                <h3>Risks</h3>
                <p>
                  Identified risks in your intelligence context.
                </p>
              </div>

              <span className="intelligence-count">
                {intelligence.risks.length}
              </span>
            </div>

            {intelligence.risks.length > 0 ? (
              <div className="intelligence-list">
                {intelligence.risks.map((risk) => (
                  <article
                    className="intelligence-item"
                    key={risk.id}
                  >
                    <div className="intelligence-item-header">
                      <h4>{risk.title}</h4>

                      {risk.severity && (
                        <span className="intelligence-status">
                          {formatStatus(risk.severity)}
                        </span>
                      )}
                    </div>

                    {risk.description && (
                      <p className="intelligence-item-description">
                        {risk.description}
                      </p>
                    )}

                    <div className="intelligence-sources">
                      <span>Sources</span>

                      <span>
                        {risk.source_chunk_ids.length}
                      </span>
                    </div>
                  </article>
                ))}
              </div>
            ) : (
              <EmptyState
                title="No risks"
                message="No risks are currently stored."
              />
            )}
          </section>
        </div>
      )}
    </section>
  );
}

export default IntelligencePage;