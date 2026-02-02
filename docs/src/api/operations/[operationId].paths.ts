import spec from '../../openapi.json'

export default {
  paths() {
    const methods = [
      'get',
      'post',
      'put',
      'patch',
      'delete',
      'options',
      'head',
    ] as const

    const out: Array<{ params: { operationId: string; pageTitle: string } }> = []
    const paths = (spec as any)?.paths ?? {}

    for (const [path, def] of Object.entries<any>(paths)) {
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
