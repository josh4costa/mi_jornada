<!-- kit:inicio — reglas comunes del equipo de Josué (kit 1.3.2). `nueva-app.sh --actualizar-app` reemplaza este bloque; lo propio de la app va fuera de él. -->
Habla y documenta en español.

## Formato de respuesta
Siempre con esta estructura, también en respuestas cortas y después de un error:
1. **Qué pasó**: de 1 a 3 frases con el resultado o el hallazgo y por qué.
2. **Detalle**: solo si aporta; lista o tabla corta.
3. **Tu turno**: solo si Josué debe hacer algo. Pasos numerados; cada uno dice dónde (equipo, carpeta y
   usuario) y trae el comando exacto en un bloque listo para copiar, sin marcadores por llenar.
4. **Después**: qué debe ver si salió bien y qué pegarte, o cuál es el siguiente paso.
Si no le toca nada, termina con «No tienes que hacer nada.»

## Git y GitHub
1. Al empezar cada tarea: `git fetch`. Si la rama actual ya se fusionó en `origin/main` o estás atrás, cámbiate a
   `main` y haz `git pull --ff-only`; dilo en una línea.
2. Una rama por cambio. Al terminar: commit, `git push -u origin <rama>`, `gh pr create` con resumen y nota de
   despliegue; si el repo tiene GitHub Actions, espera `gh pr checks --watch`. Dale a Josué el enlace del PR.
3. Merge solo con su «sí» explícito: `gh pr merge --squash --delete-branch` y luego `git checkout main && git pull --ff-only`.
4. Nunca push a `main` ni `--force` (el guardián lo bloquea).

## Diseño
Nunca elijas tú el diseño visual. Si SPEC.md (o el documento de la app) no tiene «## Diseño», pregunta:
1) El Pollo Loco, 2) Taco Palenque, 3) Grupo neutro, 4) Diseño propio con frontend-design — o que escriba `/diseno`.

## Secretos
No leas `.env` ni llaves (el guardián y los permisos lo bloquean). Para saber qué variables existen, usa
`.env.example` (o el equivalente de la app). Variables nuevas: en el ejemplo sin valor real, y dile a Josué cuáles poner.
<!-- kit:fin -->
