type CitationLike = {
  chunk_id?: unknown
  content?: unknown
  filepath?: unknown
  id?: unknown
  metadata?: unknown
  part_index?: unknown
  reindex_id?: unknown
  title?: unknown
  url?: unknown
}

const CITATION_DEBUG_STORAGE_KEY = 'dfa.citationDebug'

const hasText = (value: unknown): boolean => typeof value === 'string' && value.trim().length > 0

export const isCitationDebugEnabled = (): boolean => {
  if (typeof window === 'undefined') {
    return false
  }

  try {
    return window.localStorage.getItem(CITATION_DEBUG_STORAGE_KEY) === '1'
  } catch {
    return false
  }
}

export const citationDebugLog = (event: string, payload?: unknown): void => {
  if (!isCitationDebugEnabled()) {
    return
  }

  if (payload === undefined) {
    console.debug('[CITATION_DEBUG]', event)
    return
  }

  console.debug('[CITATION_DEBUG]', event, payload)
}

export const summarizeCitationForDebug = (citation: CitationLike) => {
  const content = citation.content
  const metadata = citation.metadata

  return {
    title: citation.title ?? null,
    filepath: citation.filepath ?? null,
    url: citation.url ?? null,
    id: citation.id ?? null,
    chunk_id: citation.chunk_id ?? null,
    reindex_id: citation.reindex_id ?? null,
    part_index: citation.part_index ?? null,
    hasTitle: hasText(citation.title),
    hasFilepath: hasText(citation.filepath),
    hasUrl: hasText(citation.url),
    hasId: hasText(citation.id),
    contentLength: typeof content === 'string' ? content.length : 0,
    metadataLength: typeof metadata === 'string' ? metadata.length : 0
  }
}
