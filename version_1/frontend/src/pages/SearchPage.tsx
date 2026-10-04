import { useState, type FormEvent } from "react";

import {
  ApiError,
  searchDocuments,
  type SearchResponse,
} from "../lib/api";
import ErrorState from "../components/feedback/ErrorState";
import LoadingState from "../components/feedback/LoadingState";

const DEFAULT_TOP_K = 5;
const MIN_TOP_K = 1;
const MAX_TOP_K = 50;

function SearchPage() {
  const [query, setQuery] = useState("");
  const [topK, setTopK] = useState(String(DEFAULT_TOP_K));

  const [isSearching, setIsSearching] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [searchResponse, setSearchResponse] =
    useState<SearchResponse | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    setErrorMessage(null);
    setSearchResponse(null);

    const trimmedQuery = query.trim();

    if (!trimmedQuery) {
      setErrorMessage("Please enter a search query.");
      return;
    }

    const parsedTopK = Number(topK);

    if (
      !Number.isInteger(parsedTopK) ||
      parsedTopK < MIN_TOP_K ||
      parsedTopK > MAX_TOP_K
    ) {
      setErrorMessage(
        `Result count must be an integer between ${MIN_TOP_K} and ${MAX_TOP_K}.`,
      );
      return;
    }

    setIsSearching(true);

    try {
      const response = await searchDocuments({
        query: trimmedQuery,
        top_k: parsedTopK,
      });

      setSearchResponse(response);
    } catch (error) {
      if (error instanceof ApiError) {
        setErrorMessage(error.message);
      } else if (error instanceof Error) {
        setErrorMessage(error.message);
      } else {
        setErrorMessage("Unable to complete the search.");
      }
    } finally {
      setIsSearching(false);
    }
  }

  return (
    <section className="page search-page">
      <div className="page-header">
        <p className="page-eyebrow">RETRIEVAL</p>
        <h2>Search</h2>
        <p className="page-description">
          Search across your personal knowledge base.
        </p>
      </div>

      <div className="search-card">
        <form className="search-form" onSubmit={handleSubmit}>
          <div className="form-field">
            <label htmlFor="search-query">Query</label>

            <input
              id="search-query"
              type="text"
              value={query}
              onChange={(event) => {
                setQuery(event.target.value);
                setErrorMessage(null);
              }}
              placeholder="Search your knowledge base"
              disabled={isSearching}
            />
          </div>

          <div className="search-form-row">
            <div className="form-field search-top-k-field">
              <label htmlFor="search-top-k">Results</label>

              <input
                id="search-top-k"
                type="number"
                step={1}
                value={topK}
                onChange={(event) => {
                  setTopK(event.target.value);
                  setErrorMessage(null);
                }}
                disabled={isSearching}
              />

              <p className="form-help">
                Number of results to retrieve, from {MIN_TOP_K} to{" "}
                {MAX_TOP_K}.
              </p>
            </div>

            <button
              type="submit"
              className="primary-button"
              disabled={isSearching}
            >
              {isSearching ? "Searching..." : "Search"}
            </button>
          </div>
        </form>
      </div>

      {errorMessage && (
        <ErrorState
          title="Search failed"
          message={errorMessage}
        />
      )}

      {isSearching && (
        <LoadingState message="Searching your knowledge base..." />
      )}

      {searchResponse && !isSearching && (
  <div className="search-results">
    <div className="search-results-header">
      <div>
        <p className="search-results-label">SEARCH RESULTS</p>
        <h3>
          {searchResponse.results.length} result
          {searchResponse.results.length === 1 ? "" : "s"}
        </h3>
      </div>

      <div className="search-results-query">
        <span>Query</span>
        <strong>{searchResponse.query}</strong>
      </div>
    </div>

    {searchResponse.results.length === 0 ? (
      <div className="search-results-empty">
        <p className="feedback-title">No results found</p>
        <p className="feedback-message">
          No matching content was found for this query.
        </p>
      </div>
    ) : (
      <div className="search-result-list">
        {searchResponse.results.map((result, index) => (
          <article
            key={result.chunk_id}
            className="search-result-card"
          >
            <div className="search-result-header">
              <div className="search-result-position">
                Result {index + 1}
              </div>

              <div className="search-result-score">
                Score: {result.score.toFixed(4)}
              </div>
            </div>

            <div className="search-result-content">
              {result.content}
            </div>

            <dl className="search-result-meta">
              <div>
                <dt>Document ID</dt>
                <dd>{result.document_id}</dd>
              </div>

              <div>
                <dt>Chunk ID</dt>
                <dd>{result.chunk_id}</dd>
              </div>
            </dl>
          </article>
        ))}
      </div>
    )}
  </div>
)}
    </section>
  );
}

export default SearchPage;