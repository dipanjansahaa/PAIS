import { useState, type FormEvent } from "react";

import {
  ApiError,
  uploadDocument,
  type DocumentResponse,
} from "../lib/api";
import EmptyState from "../components/feedback/EmptyState";
import ErrorState from "../components/feedback/ErrorState";
import LoadingState from "../components/feedback/LoadingState";

function DocumentsPage() {
  const [file, setFile] = useState<File | null>(null);
  const [title, setTitle] = useState("");
  const [sourceType, setSourceType] = useState("");

  const [isUploading, setIsUploading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [uploadedDocument, setUploadedDocument] =
    useState<DocumentResponse | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (isUploading) {
      return;
    }

    setErrorMessage(null);
    setUploadedDocument(null);

    if (!file) {
      setErrorMessage("Please select a document to upload.");
      return;
    }

    if (!title.trim()) {
      setErrorMessage("Please enter a document title.");
      return;
    }

    if (!sourceType.trim()) {
      setErrorMessage("Please enter a source type.");
      return;
    }

    setIsUploading(true);

    try {
      const document = await uploadDocument(
        file,
        title.trim(),
        sourceType.trim(),
      );

      setUploadedDocument(document);
      setFile(null);
      setTitle("");
      setSourceType("");
    } catch (error) {
      if (error instanceof ApiError) {
        setErrorMessage(error.message);
      } else if (error instanceof Error) {
        setErrorMessage(error.message);
      } else {
        setErrorMessage("Unable to upload the document.");
      }
    } finally {
      setIsUploading(false);
    }
  }

  return (
    <section className="page documents-page">
      <div className="page-header">
        <p className="page-eyebrow">KNOWLEDGE BASE</p>
        <h2>Documents</h2>
        <p className="page-description">
          Upload documents that power your personal knowledge base.
        </p>
      </div>

      <div className="documents-layout">
        <div className="document-upload-card">
          <div className="section-header">
            <div>
              <h3>Upload document</h3>
              <p>
                Add a document to the PAIS knowledge base.
              </p>
            </div>
          </div>

          <form className="document-upload-form" onSubmit={handleSubmit}>
            <div className="form-field">
              <label htmlFor="document-file">File</label>

              <input
                id="document-file"
                type="file"
                onChange={(event) => {
                  setFile(event.target.files?.[0] ?? null);
                  setErrorMessage(null);
                }}
                disabled={isUploading}
              />

              {file && (
                <p className="form-help">
                  Selected: {file.name}
                </p>
              )}
            </div>

            <div className="form-field">
              <label htmlFor="document-title">Title</label>

              <input
                id="document-title"
                type="text"
                value={title}
                onChange={(event) => {
                  setTitle(event.target.value);
                  setErrorMessage(null);
                }}
                placeholder="Document title"
                disabled={isUploading}
              />
            </div>

            <div className="form-field">
              <label htmlFor="document-source-type">
                Source type
              </label>

              <input
                id="document-source-type"
                type="text"
                value={sourceType}
                onChange={(event) => {
                  setSourceType(event.target.value);
                  setErrorMessage(null);
                }}
                placeholder="e.g. notes, markdown, pdf"
                disabled={isUploading}
              />
            </div>

            {errorMessage && (
              <ErrorState
                title="Upload failed"
                message={errorMessage}
              />
            )}

            {isUploading && (
              <LoadingState message="Uploading and ingesting document..." />
            )}

            <button
              type="submit"
              className="primary-button"
              disabled={isUploading}
            >
              {isUploading ? "Uploading..." : "Upload document"}
            </button>
          </form>
        </div>

        <div className="document-result-card">
          <div className="section-header">
            <div>
              <h3>Latest upload</h3>
              <p>
                The most recent document successfully added to PAIS.
              </p>
            </div>
          </div>

          {uploadedDocument ? (
            <div className="document-result">
              <div className="document-result-title">
                {uploadedDocument.title}
              </div>

              <dl className="document-result-meta">
                <div>
                  <dt>File</dt>
                  <dd>
                    {uploadedDocument.file_name ?? "Unknown"}
                  </dd>
                </div>

                <div>
                  <dt>Source type</dt>
                  <dd>{uploadedDocument.source_type}</dd>
                </div>

                <div>
                  <dt>MIME type</dt>
                  <dd>
                    {uploadedDocument.mime_type ?? "Unknown"}
                  </dd>
                </div>

                <div>
                  <dt>ID</dt>
                  <dd>{uploadedDocument.id}</dd>
                </div>
              </dl>
            </div>
          ) : (
            <EmptyState
              title="No document uploaded yet"
              message="Upload a document to see its details here."
            />
          )}
        </div>
      </div>
    </section>
  );
}

export default DocumentsPage;