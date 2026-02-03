import spec from '../../openapi.json'

type HttpMethod = 'get' | 'post' | 'put' | 'patch' | 'delete' | 'options' | 'head'

type OpenAPIOperationObject = {
  operationId?: string
  summary?: string
}

type OpenAPIPathItemObject = Partial<Record<HttpMethod, OpenAPIOperationObject>>

type OpenAPISpec = {
  paths?: Record<string, OpenAPIPathItemObject>
}

export default {
  paths() {
    const methods: readonly HttpMethod[] = [
      'get',
      'post',
      'put',
      'patch',
      'delete',
      'options',
      'head',
    ]

    const out: Array<{ params: { operationId: string; pageTitle: string } }> = []
    const paths = (spec as OpenAPISpec).paths ?? {}

    for (const [path, def] of Object.entries(paths)) {
      for (const method of methods) {
        const op = def?.[method]
        if (!op) continue
        const operationId = op.operationId
        if (!operationId) continue
        const pageTitle = op.summary || `${method.toUpperCase()} ${path}`
        out.push({ params: { operationId, pageTitle } })
      }
    }

    return out
  },
}
