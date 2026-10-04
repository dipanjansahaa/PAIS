import { useState, type FormEvent } from "react";

import {
  ApiError,
  queryDocuments,
  type QueryResponse,
} from "../lib/api";
import EmptyState from "../components/feedback/EmptyState";
import ErrorState from "../components/feedback/ErrorState";
import LoadingState from "../components/feedback/LoadingState";

const DEFAULT_TOP_K = 5;
const DEFAULT_TEMPERATURE = 0;

function QueryPage() {
  const [query, setQuery] = useState("");
  const [topK, setTopK] = useState(String(DEFAULT_TOP_K));
  const [temperature, setTemperature] = useState(String(DEFAULT_TEMPERATURE));

  const [isQuerying, setIsQuerying] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [response, setResponse] = useState<QueryResponse | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    setErrorMessage(null);
    setResponse(null);

    const trimmedQuery = query.trim();

    if (!trimmedQuery) {
      setErrorMessage("Please enter a question.");
      return;
    }

    const parsedTopK = Number(topK);
    const parsedTemperature = Number(temperature);

    if (topK.trim() === "") {
      setErrorMessage("Please enter a Top K value.");
      return;
    }

    if (!Number.isInteger(parsedTopK)) {
      setErrorMessage("Top K must be a whole number.");
      return;
    }

    if (parsedTopK < 1) {
      setErrorMessage("Top K must be greater than or equal to 1.");
      return;
    }

    if (parsedTopK > 50) {
      setErrorMessage("Top K must be less than or equal to 50.");
      return;
    }

    if (temperature.trim() === "") {
      setErrorMessage("Please enter a temperature value.");
      return;
    }

    if (!Number.isFinite(parsedTemperature)) {
      setErrorMessage("Temperature must be a valid number.");
      return;
    }

    if (parsedTemperature < 0) {
      setErrorMessage("Temperature must be greater than or equal to 0.");
      return;
    }

    if (parsedTemperature > 2) {
      setErrorMessage("Temperature must be less than or equal to 2.");
      return;
    }

    setIsQuerying(true);

    try {
      const result = await queryDocuments({
        query: trimmedQuery,
        top_k: parsedTopK,
        temperature: parsedTemperature,
      });

      setResponse(result);
    } catch (error) {
      if (error instanceof ApiError) {
        setErrorMessage(error.message);
      } else if (error instanceof Error) {
        setErrorMessage(error.message);
      } else {
        setErrorMessage("Unable to process the query.");
      }
    } finally {
      setIsQuerying(false);
    }
  }

  return (
    <section className="page query-page">
      <div className="page-header">
        <p className="page-eyebrow">GROUNDED GENERATION</p>
        <h2>Query</h2>
        <p className="page-description">
          Ask questions and receive grounded answers from your knowledge base.
        </p>
      </div>

      <div className="query-layout">
        <div className="query-form-card">
          <div className="section-header">
            <div>
              <h3>Ask PAIS</h3>
              <p>
                Your question will be answered using retrieved knowledge from
                your documents.
              </p>
            </div>
          </div>

          <form className="query-form" onSubmit={handleSubmit}>
            <div className="form-field">
              <label htmlFor="query-input">Question</label>

              <textarea
                id="query-input"
                value={query}
                onChange={(event) => {
                  setQuery(event.target.value);
                  setErrorMessage(null);
                }}
                placeholder="What would you like to know?"
                rows={6}
                disabled={isQuerying}
              />

              <p className="form-help">
                Ask a question about information contained in your uploaded
                documents.
              </p>
            </div>

            <div className="query-options">
              <div className="form-field">
                <label htmlFor="query-top-k">Top K</label>

                <input
                  id="query-top-k"
                  type="text"
                  inputMode="numeric"
                  value={topK}
                  onChange={(event) => {
                    setTopK(event.target.value);
                    setErrorMessage(null);
                  }}
                  disabled={isQuerying}
                />

                <p className="form-help">
                  Number of retrieved chunks used as context.
                </p>
              </div>

              <div className="form-field">
                <label htmlFor="query-temperature">Temperature</label>

                <input
                  id="query-temperature"
                  type="text"
                  inputMode="decimal"
                  value={temperature}
                  onChange={(event) => {
                    setTemperature(event.target.value);
                    setErrorMessage(null);
                  }}
                  disabled={isQuerying}
                />

                <p className="form-help">
                  Generation temperature.
                </p>
              </div>
            </div>

            {errorMessage && (
              <ErrorState
                title="Query failed"
                message={errorMessage}
              />
            )}

            {isQuerying && (
              <LoadingState message="Retrieving context and generating answer..." />
            )}

            <button
              type="submit"
              className="primary-button"
              disabled={isQuerying}
            >
              {isQuerying ? "Generating..." : "Ask PAIS"}
            </button>
          </form>
        </div>

        <div className="query-result-card">
          <div className="section-header">
            <div>
              <h3>Answer</h3>
              <p>
                Grounded response generated from your retrieved knowledge.
              </p>
            </div>
          </div>

          {response ? (
            <div className="query-result">
              <div className="query-answer">
                {response.answer}
              </div>

              <div className="query-result-meta">
                <span>Model: {response.model}</span>

                <span>
                  Latency: {response.latency_ms} ms
                </span>

                <span>
                  Context: {response.sources.length} source
                  {response.sources.length === 1 ? "" : "s"}
                </span>
              </div>

              {response.sources.length > 0 ? (
                <div className="query-sources">
                  <div className="query-sources-header">
                    <h4>Sources</h4>
                    <p>
                      Retrieved evidence used to generate this answer.
                    </p>
                  </div>

                  <div className="query-source-list">
                    {response.sources.map((source) => (
                      <article
                        key={source.citation_id}
                        className="query-source"
                      >
                        <div className="query-source-header">
                          <div>
                            <span className="query-source-citation">
                              {source.citation_id}
                            </span>

                            <span className="query-source-document">
                              Document: {source.document_id}
                            </span>
                          </div>
                        </div>

                        <div className="query-source-chunks">
                          {source.chunks.map((chunk) => (
                            <div
                              key={chunk.citation_id}
                              className="query-source-chunk"
                            >
                              <div className="query-source-chunk-meta">
                                <span className="query-source-chunk-citation">
                                  {chunk.citation_id}
                                </span>

                                <span>
                                  Score: {chunk.score.toFixed(4)}
                                </span>
                              </div>

                              <p className="query-source-content">
                                {chunk.content}
                              </p>
                            </div>
                          ))}
                        </div>
                      </article>
                    ))}
                  </div>
                </div>
              ) : (
                <div className="query-sources">
                  <div className="query-sources-header">
                    <h4>Sources</h4>
                    <p>
                      Retrieved evidence used to generate this answer.
                    </p>
                  </div>

                  <EmptyState
                    title="No supporting sources"
                    message="The query returned an answer, but no supporting document sources were returned."
                  />
                </div>
              )}
            </div>
          ) : (
            <div className="query-result-empty">
              <p>
                Ask a question to see a grounded answer here.
              </p>
            </div>
          )}
        </div>
      </div>
    </section>
  );
}

export default QueryPage;