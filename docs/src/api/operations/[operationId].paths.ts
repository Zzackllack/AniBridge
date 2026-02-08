import spec from "../../openapi.json";

type HttpMethod =
  | "get"
  | "post"
  | "put"
  | "patch"
  | "delete"
  | "options"
  | "head";

type OpenAPIOperationObject = {
  operationId?: string;
  summary?: string;
  description?: string;
};

type OpenAPIPathItemObject = Partial<
  Record<HttpMethod, OpenAPIOperationObject>
>;

type OpenAPISpec = {
  paths?: Record<string, OpenAPIPathItemObject>;
};

export default {
  paths() {
    const methods: readonly HttpMethod[] = [
      "get",
      "post",
      "put",
      "patch",
      "delete",
      "options",
      "head",
    ];

    const out: Array<{
      params: {
        operationId: string;
        pageTitle: string;
        pageDescription: string;
      };
    }> = [];
    const paths = (spec as OpenAPISpec).paths ?? {};

    const normalizeDescription = (value?: string) => {
      if (!value) return undefined;
      const compact = value.replace(/\s+/g, " ").trim();
      if (!compact) return undefined;
      if (compact.length <= 160) return compact;
      return `${compact.slice(0, 157).trimEnd()}...`;
    };

    for (const [path, def] of Object.entries(paths)) {
      for (const method of methods) {
        const op = def?.[method];
        if (!op) continue;
        const operationId = op.operationId;
        if (!operationId) continue;
        const pageTitle = op.summary || `${method.toUpperCase()} ${path}`;
        const pageDescription =
          normalizeDescription(op.description) ||
          `${pageTitle} endpoint reference in AniBridge API docs.`;
        out.push({ params: { operationId, pageTitle, pageDescription } });
      }
    }

    return out;
  },
};
