# La suite finale

Un test de la suite par comportement promis par le cours, du premier outil à l'image, lancés
ensemble, puis un bilan, une ligne par promesse et le module qui l'a tenue :

```bash
docker build -t pachatraining-mcp .
PACHA_IMAGE=pachatraining-mcp bash exercises/final/check.sh
# Podman : podman build -t pachatraining-mcp . puis PACHA_IMAGE=pachatraining-mcp ENGINE=podman bash exercises/final/check.sh
```

Le labo doit tourner (`./setup/install.sh`). Le script n'appelle ni modèle ni Node ; les tests
qui écrivent le font sur `PachadataTraining_m07`, comme au module 7. Chaque test listé doit
passer : un test sauté, celui de l'image sans `PACHA_IMAGE`, fait échouer le contrôle. La
dernière ligne doit être `All 19 promises kept.`

---

# The final check

One test of the suite for each behaviour the course promised, from the first tool to the image,
run together, then a summary, one line per promise with the module that kept it. Build the
image (`docker build -t pachatraining-mcp .`), then run
`PACHA_IMAGE=pachatraining-mcp bash exercises/final/check.sh` (with Podman, `ENGINE=podman` in
front), with the lab started. It calls neither a model nor Node; the tests that write do it on
`PachadataTraining_m07`. Every listed test must pass: a skipped one fails the check. The last
line must be `All 19 promises kept.`
