# Historical materials

[Current overview](../../README.md)

The files here preserve the previous README, container image definition and two original Kubernetes manifests from commit `ca8d25b`. They describe the earlier operator-specific workflow, not recommended defaults for version 0.2. The original manifests used a privileged container, LoadBalancer and an auth-file mount; they are retained for history and are not deployed by the demo or CI.

- [Earlier README](README.v1.md)
- [Earlier Dockerfile](Dockerfile.v1)
- [Root deployment example](deployment-root.yaml)
- [k8s deployment example](deployment-k8s.yaml)
- [Original source tree](https://github.com/li1fang/headless-bridge/tree/ca8d25bd3e50fd9ce6fc9aafa45e5640178ef7ba)

The standalone [rget script](../../scripts/rget) is unchanged and is not part of the service execution path. Its download and hashing behavior is not covered by the new HTTP fixture tests.
