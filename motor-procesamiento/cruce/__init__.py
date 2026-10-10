"""Cruce con el sistema de la tienda (sustituye a P4 mientras no llegue).

El motor observa (`salida/observaciones.json`); el cruce compara contra el sistema
(planograma, precios e inventario), calcula el dinero y escribe el `hallazgos.json` que
lee el tablero. `cruce.api` es la API local del modo jurado y `cruce.publicar` copia todo
a `Road2Tech/Frontend/public/`.
"""
