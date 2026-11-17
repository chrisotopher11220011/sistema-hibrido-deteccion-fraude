# ADR 0012: Contribución por variable con SHAP para árboles

- **Estado:** Aceptada
- **Fecha:** 2026-11-17
- **Fase en la que se aplica:** 3 (y la API desde la 4)

## Contexto

La sección 11 pide, para cada alerta, las variables que más pesaron en la puntuación, «con un método documentado y verificado para `IsolationForest`», y propone como ejemplos SHAP para árboles o DIFFI. La sección 24 dejaba pendiente comprobar que esos métodos admiten el `IsolationForest` de scikit-learn.

Lo comprobado el 2026-11-17 (UTC):

- **SHAP 0.54.1.** `shap.TreeExplainer` reconoce `sklearn.ensemble.IsolationForest` en su código (`shap/explainers/_tree.py`, clase `IsoTree`). Recalcula el valor de cada hoja como profundidad más c(n), igual que scikit-learn, y respeta las variables de cada árbol (`estimators_features_`). Con scikit-learn 1.9.1, la suma del valor esperado y los valores SHAP reconstruye la profundidad media de cada fila, y de ella `score_samples`, con un error máximo de 3·10⁻¹⁶. Tarda alrededor de 1 ms por fila. Licencia MIT; requiere Python ≥ 3.12 y ya no depende de numba.
- **DIFFI.** No hay paquete en PyPI (`diffi` y `DIFFI` devuelven 404): solo el código que acompaña al artículo, sin mantenimiento ni versiones.

## Decisión

Se usa `shap.TreeExplainer` (versión fijada en `uv.lock`) sobre el modelo entrenado, sin datos de fondo (modo de dependencia por el camino del árbol, el que SHAP aplica por defecto a modelos de árboles).

SHAP explica la profundidad media de aislamiento. Como una profundidad menor es más anómala, el **peso** de una variable es el valor SHAP con el signo cambiado: positivo empuja hacia «más anómalo». Para cada alerta se informan las `k` variables de mayor peso (`config/modelo.yaml`, `contribuciones.k`).

Una prueba unitaria comprueba la aditividad con las versiones instaladas: si una versión nueva de scikit-learn o de SHAP la rompe, la CI lo detecta antes de que la explicación deje de corresponder a la puntuación.

## Consecuencias

- Explicación local, exacta respecto del modelo y comprobable en cada ejecución.
- Las variables `V1` a `V28` son componentes anónimos: la explicación dice cuáles pesaron, no por qué. Se presenta como explicación técnica, nunca como motivo del fraude.
- `Amount` también entra en la explicación; las reglas tienen su propia razón en texto.
- Añade la dependencia `shap` a la imagen (unos 2 MB más scipy, que scikit-learn ya trae).
- Antes de citar SHAP en la ponencia hay que leer su artículo original (Lundberg y Lee, 2017; Lundberg et al., 2020 para árboles).
