#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
OUTPUT_DIR="${ROOT_DIR}/ci-artifacts/helm"

mkdir -p "${OUTPUT_DIR}"

charts=(
  "alb-controller;aws-load-balancer-controller;https://aws.github.io/eks-charts;1.7.1;platform/helm/alb-controller"
  "external-dns;external-dns;https://kubernetes-sigs.github.io/external-dns/;1.15.2;platform/helm/external-dns"
  "calico;tigera-operator;https://docs.tigera.io/calico/charts;v3.27.0;platform/helm/calico"
  "kube-prometheus-stack;kube-prometheus-stack;https://prometheus-community.github.io/helm-charts;56.21.1;platform/helm/kube-prometheus-stack"
  "grafana;grafana;https://grafana.github.io/helm-charts;8.5.9;platform/helm/grafana"
)

for chart_entry in "${charts[@]}"; do
  IFS=';' read -r NAME CHART REPO VERSION BASE_DIR <<<"${chart_entry}"
  for ENV in dev prod; do
    PATCH_FILE="${ROOT_DIR}/${BASE_DIR}/${ENV}/patch-application.yaml"
    if [[ ! -f "${PATCH_FILE}" ]]; then
      echo "⚠️  Skipping ${NAME} (${ENV}) – patch file not found: ${PATCH_FILE}" >&2
      continue
    fi
    VALUES_CONTENT="$(
python3 - "${PATCH_FILE}" <<'PY'
import sys, yaml, pathlib
patch = pathlib.Path(sys.argv[1]).read_text()
data = yaml.safe_load(patch) or {}
values = (((data.get("spec") or {}).get("source") or {}).get("helm") or {}).get("valuesObject")
if values is None:
    yaml.safe_dump({}, sys.stdout, sort_keys=False)
else:
    yaml.safe_dump(values, sys.stdout, sort_keys=False)
PY
)"
    TMP_VALUES="$(mktemp)"
    printf "%s" "${VALUES_CONTENT}" > "${TMP_VALUES}"
    OUTPUT_FILE="${OUTPUT_DIR}/${NAME}-${ENV}.yaml"
    echo "::group::helm template ${NAME} (${ENV})"
    helm template "${ENV}-${NAME}" "${CHART}" \
      --repo "${REPO}" \
      --version "${VERSION}" \
      --namespace "ci-${NAME}-${ENV}" \
      -f "${TMP_VALUES}" \
      > "${OUTPUT_FILE}"
    echo "Rendered manifest saved to ${OUTPUT_FILE}"
    echo "::endgroup::"
    rm -f "${TMP_VALUES}"
  done
done

ls -1 "${OUTPUT_DIR}"

