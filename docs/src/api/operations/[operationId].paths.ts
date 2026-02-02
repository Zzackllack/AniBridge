import { usePaths } from 'vitepress-openapi'
import spec from '../../public/openapi.json' with { type: 'json' }

export default {
  paths() {
    return usePaths({ spec })
      .getPathsByVerbs()
      .map(({ operationId, summary, verb, path }) => ({
        params: {
          operationId,
          pageTitle: summary || `${verb.toUpperCase()} ${path}`,
        },
      }))
  },
}
