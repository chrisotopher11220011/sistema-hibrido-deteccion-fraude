# ADR 0002: Fuente de datos y verificación de integridad

- **Estado:** Aceptada
- **Fecha:** 2026-11-16
- **Fase en la que se aplica:** 2

## Contexto

El conjunto *Credit Card Fraud Detection* (ULB y Worldline) pesa unos 150 MB y no puede ir al repositorio. Kaggle exige cuenta y credenciales; OpenML publica el mismo conjunto (identificador 1597) sin credenciales. OpenML marca `Time` como identificador de fila y algunas bibliotecas la omiten al descargar.

## Decisión

`tareas preparar` descarga el conjunto de OpenML al ejecutar. Como alternativa manual, quien ejecuta puede dejar el archivo de Kaggle en `datos/crudos/creditcard.csv`. Tras la descarga se comprueban filas (284.807), fraudes (492) y columnas. La primera ejecución N3 fija la huella SHA-256 y las siguientes la verifican. El modelo no depende de `Time`: si falta, se registra y se continúa.

## Consecuencias

- No hacen falta cuentas ni secretos para ejecutar.
- Que OpenML entregue lo mismo que Kaggle es el supuesto S3 hasta que `datos.json` lo confirme.
- La huella no existe hasta la primera ejecución N3; antes solo protegen los conteos.
- Sin `Time` se pierde el análisis secundario de partición temporal, que se omite dejando constancia.
