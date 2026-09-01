# Kubernetes deployment baseline

This Kustomize base deploys the stateless web tier, Node.js API and processor microservices, and an autoscaled AI-worker tier. PostgreSQL, Ollama/Qwen, optional enterprise event infrastructure and ingress are endpoints rather than bundled stateful workloads so each environment can use approved managed or in-house services.

## Before applying

1. Build and push the four images to an approved private registry, then replace the image names/tags in `base/kustomization.yaml`.
2. Replace the database, Ollama, allowed-origin and Entra issuer values in `base/configmap.yaml`.
3. Create the namespace, then create the runtime secret without writing it to a file or Git:

   ```bash
   kubectl apply -f deploy/k8s/base/namespace.yaml
   kubectl -n ies create secret generic ies-runtime-secrets \
     --from-literal=DATABASE_PASSWORD=REPLACE_WITH_SECRET_MANAGER_VALUE
   ```

4. Configure a private-registry image pull secret when required.
5. Review the storage class. The baseline uses one API and one processor replica with `ReadWriteOnce`; horizontal scaling requires encrypted shared storage or an object-storage adapter.
6. Expose the `web` service through the environment's approved ingress/gateway with TLS.

Render before applying:

```bash
kubectl kustomize deploy/k8s/base
kubectl apply -k deploy/k8s/base
```

Network policies deny traffic by default and allow only web-to-API, processor-to-AI-worker and declared dependency ports. Confirm that the cluster CNI enforces `NetworkPolicy` and tighten external dependency destinations to the environment's namespaces or IP blocks.
