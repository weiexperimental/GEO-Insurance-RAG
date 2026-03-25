export interface SystemHealth {
  cluster: { status: string; number_of_nodes: number }
  nodes: Record<string, any>
  overview: {
    cluster_status: string
    documents: string
    entities: string
    relationships: string
    chunks: string
    llm_cache: string
    index_size: string
    pending: string
    failed: string
    indices: any[]
  }
  knn: Record<string, any>
}

export interface IngestionStatus {
  active: Array<{
    document_id: string
    file_name: string
    file_path: string
    status: string
    metadata: Record<string, any>
    chunks_count?: number | null
    created_at?: string
    updated_at?: string
  }>
  pipeline: { busy: boolean; docs?: number }
}

export interface WsMessage {
  type: 'system_health' | 'ingestion_update' | 'log_entry' | 'snapshot'
  data: any
  timestamp: string
}

export interface Document {
  document_id: string
  file_name: string
  file_path?: string
  status: string
  metadata: {
    company?: string
    product_name?: string
    product_type?: string
    document_type?: string
    document_date?: string
  }
  chunks_count?: number | null
  created_at?: string
  updated_at?: string
}

export interface GraphNode {
  id: string
  entity_type: string
  description: string
  file_path: string
  source_ids: string[]
  connectionCount?: number
}

export interface GraphEdge {
  id: string
  source: string
  target: string
  weight: number
  description: string
  keywords: string
  file_path: string
}

export interface GraphData {
  nodes: GraphNode[]
  edges: GraphEdge[]
}

export interface EntityDetail {
  entity: GraphNode
  connections: Array<{
    id: string
    other_entity: string
    direction: 'incoming' | 'outgoing'
    weight: number
    description: string
    keywords: string
  }>
}

export interface SimilarEntity {
  entity_id: string
  entity_name: string
  description: string
  file_path: string
  vector_similarity: number
  name_similarity: number
  reason: string
}

export interface LogEntry {
  timestamp?: string
  document?: string
  stage?: string
  status?: string
  duration_ms?: number
  details?: Record<string, any>
  raw?: string
}

// ─── Query Playground ─────────────────────────────────────────────────────────

export interface PlaygroundQueryRequest {
  query: string
  mode: 'local' | 'global' | 'hybrid' | 'naive' | 'mix'
  top_k: number
  chunk_top_k: number
  enable_rerank: boolean
}

export interface PlaygroundCompareRequest {
  query: string
  params_a: Omit<PlaygroundQueryRequest, 'query'>
  params_b: Omit<PlaygroundQueryRequest, 'query'>
}

export interface PlaygroundEntity {
  entity_name: string
  entity_type: string
  description: string
  source_id: string
  file_path: string
  reference_id: string
}

export interface PlaygroundRelationship {
  src_id: string
  tgt_id: string
  description: string
  keywords: string
  weight: number
  reference_id: string
}

export interface PlaygroundChunk {
  content: string
  file_path: string
  chunk_id: string
  reference_id: string
}

export interface PlaygroundTiming {
  total_ms: number
  retrieval_ms?: number
}

export interface PlaygroundProcessingInfo {
  total_entities_found: number
  entities_after_truncation: number
  total_relations_found: number
  relations_after_truncation: number
  merged_chunks_count: number
  final_chunks_count: number
}

export interface PlaygroundResult {
  status: string
  data: {
    keywords: { high_level: string[]; low_level: string[] }
    entities: PlaygroundEntity[]
    relationships: PlaygroundRelationship[]
    chunks: PlaygroundChunk[]
    references: { reference_id: string; file_path: string }[]
  }
  metadata: {
    query_mode: string
    processing_info: PlaygroundProcessingInfo
  }
  full_prompt: string | null
  llm_response: string | null
  timing: PlaygroundTiming
}

export interface PlaygroundCompareResult {
  result_a: PlaygroundResult
  result_b: PlaygroundResult
}

export type ChunkRating = 'relevant' | 'partial' | 'irrelevant' | null

// ─── Chunk Inspector ─────────────────────────────────────────────────────────

export type ChunkQuality = 'good' | 'warning' | 'bad'

export interface ChunkItem {
  id: string
  content: string
  tokens: number
  original_type: string
  file_path: string
  full_doc_id: string
  page_idx: number
  chunk_order_index: number
  is_multimodal: boolean
  modal_entity_name: string
  quality: ChunkQuality
  quality_reasons: string[]
  create_time: number
  update_time: number
}

export interface ChunksListResponse {
  chunks: ChunkItem[]
  total: number
  page: number
  size: number
}

export interface ChunkQualityStats {
  good: number
  warning: number
  bad: number
  total: number
}

export interface TokenBucket {
  range: string
  count: number
}

export interface TokenDistribution {
  buckets: TokenBucket[]
}

// ─── Evaluation ──────────────────────────────────────────────────────────────

export interface QAPair {
  id: string
  question: string
  expected_answer: string
  source_doc: string
  category: string
  difficulty: string
  status: 'draft' | 'approved' | 'rejected'
  created_by: 'manual' | 'auto_generated'
  created_at: number
  updated_at: number
}

export interface QAPairsResponse {
  pairs: QAPair[]
  total: number
  page: number
  size: number
}

export interface EvalScores {
  answer_correctness: number
  faithfulness: number
  context_relevancy: number
}

export interface EvalResultItem {
  qa_pair_id: string
  question: string
  expected_answer: string
  actual_response: string
  retrieved_chunks_count: number
  scores: EvalScores
}

export interface EvalRun {
  run_id: string
  timestamp: number
  total_pairs: number
  scores: EvalScores
  status: 'running' | 'completed' | 'failed'
  results?: EvalResultItem[]
}
