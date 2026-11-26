# Consultas origen–destino — ruta 801

Supuestos (calidad `unverified`): caminata en línea recta × 1,3 a 4–5 km/h, caminata máxima 1000 m por extremo, intervalo entre buses 10–20 min y tiempos de viaje del grafo (RGT-131). Alternativas ordenadas por el peor caso del rango de tiempo.

## Resumen

| Consulta | Mejor opción         | Tiempo    | A pie | Resultado esperado                                                                                                     |
| -------- | -------------------- | --------- | ----- | ---------------------------------------------------------------------------------------------------------------------- |
| Q1       | Ruta 801 #075 → #086 | 31–46 min | 456 m | Viaje largo en el sentido 0, hacia la terminal                                                                         |
| Q2       | Ruta 801 #087 → #106 | 44–65 min | 315 m | Viaje en el sentido 1, de regreso                                                                                      |
| Q3       | Ruta 801 #101 → #105 | 15–23 min | 199 m | En la misma esquina hay paradas de ida (#074) y de regreso (#101): el planificador debe abordar en el sentido correcto |
| Q4       | Caminar              | 6–8 min   | 504 m | Caminar debería ser mejor que tomar el bus                                                                             |
| Q5       | Sin itinerario       | —         | —     | Fuera de la cobertura de la ruta: no debería haber itinerario                                                          |

## Limitaciones

- Una sola ruta (801): no hay transbordos con otras rutas de TuBus ni con Transmetro.
- Caminata estimada en línea recta con factor de rodeo; no considera la red peatonal, pasarelas ni cruces (requiere OpenStreetMap).
- Sin frecuencias ni horarios oficiales: la espera es un supuesto y no se consideran las ventanas de servicio (5:30–19:00 de lunes a sábado).
- Tiempos de viaje estimados con una velocidad comercial supuesta; no reflejan tráfico ni variación por hora del día.
- Ubicaciones de paradas tomadas de la capa municipal sin validación en campo: 14 de 47 tienen la ubicación no verificada y 23 alguna discrepancia con el rutero.
- Sin tarifas ni medios de pago estructurados.

## Q1. Cerca de Parque Kaminaljuyú (#075) → cerca de Parque de la Industria (#086)

_Propósito:_ Viaje largo en el sentido 0, hacia la terminal

**Alternativa 1 — Ruta 801: #075 → #086** · 31–46 min · 456 m a pie

1. Camina unos 196 m (2–3 min) hasta la parada #075: Parque Kaminaljuyú, diagonal 24 y 13 calle, Colonia Ciudad de Plata I.
2. Toma la ruta 801 con dirección a Terminal 4a av. y 4a calle, zona 9; pasa aproximadamente cada 10–20 min.
3. Viaja 11 paradas (21–29 min) y bájate en la parada #086: Parque de la Industria, avenida La Castellana y 8a calle, Cantón Guarda Viejo.
4. Camina unos 260 m (3–4 min) hasta tu destino.

**Alternativa 2 — Ruta 801: #075 → #085** · 33–48 min · 697 m a pie

1. Camina unos 196 m (2–3 min) hasta la parada #075: Parque Kaminaljuyú, diagonal 24 y 13 calle, Colonia Ciudad de Plata I.
2. Toma la ruta 801 con dirección a Terminal 4a av. y 4a calle, zona 9; pasa aproximadamente cada 10–20 min.
3. Viaja 10 paradas (20–28 min) y bájate en la parada #085: Avenida La Castellana y 9a calle, Cantón Tívoli.
4. Camina unos 501 m (6–8 min) hasta tu destino.

**Alternativa 3 — Ruta 801: #075 → #087** · 38–54 min · 744 m a pie

1. Camina unos 196 m (2–3 min) hasta la parada #075: Parque Kaminaljuyú, diagonal 24 y 13 calle, Colonia Ciudad de Plata I.
2. Toma la ruta 801 con dirección a Terminal 4a av. y 4a calle, zona 9; pasa aproximadamente cada 10–20 min.
3. Viaja 12 paradas (24–33 min) y bájate en la parada #087: Terminal, 4a avenida y 4a calle, Cantón Tívoli.
4. Camina unos 548 m (7–8 min) hasta tu destino.

**Evaluación:**

- Paradas de abordaje o descenso con ubicación no verificada: #075, #086; requieren validación en campo.

## Q2. Cerca de la terminal (#087) → Colonia Bethania (#106)

_Propósito:_ Viaje en el sentido 1, de regreso

**Alternativa 1 — Ruta 801: #087 → #106** · 44–65 min · 315 m a pie

1. Camina unos 184 m (2–3 min) hasta la parada #087: Terminal, 4a avenida y 4a calle, Cantón Tívoli.
2. Toma la ruta 801 con dirección a Parque Los Pinos, zona 7; pasa aproximadamente cada 10–20 min.
3. Viaja 19 paradas (35–50 min) y bájate en la parada #106: 33 avenida y 30 calle, Colonia Bethania.
4. Camina unos 131 m (2 min) hasta tu destino.

**Alternativa 2 — Ruta 801: #087 → #107** · 47–68 min · 435 m a pie

1. Camina unos 184 m (2–3 min) hasta la parada #087: Terminal, 4a avenida y 4a calle, Cantón Tívoli.
2. Toma la ruta 801 con dirección a Parque Los Pinos, zona 7; pasa aproximadamente cada 10–20 min.
3. Viaja 20 paradas (37–52 min) y bájate en la parada #107: 33 avenida y 33 calle.
4. Camina unos 251 m (3–4 min) hasta tu destino.

**Alternativa 3 — Ruta 801: #087 → #105** · 47–69 min · 688 m a pie

1. Camina unos 184 m (2–3 min) hasta la parada #087: Terminal, 4a avenida y 4a calle, Cantón Tívoli.
2. Toma la ruta 801 con dirección a Parque Los Pinos, zona 7; pasa aproximadamente cada 10–20 min.
3. Viaja 18 paradas (34–48 min) y bájate en la parada #105: 33 avenida y 26 calle, Colonia Bethania.
4. Camina unos 504 m (6–8 min) hasta tu destino.

## Q3. Ciudad de Plata, lado del regreso (#101) → Colonia Kjell Laugerud (#069)

_Propósito:_ En la misma esquina hay paradas de ida (#074) y de regreso (#101): el planificador debe abordar en el sentido correcto

**Alternativa 1 — Ruta 801: #101 → #105** · 15–23 min · 199 m a pie

1. Camina unos 39 m (0–1 min) hasta la parada #101: Diagonal 24 y 14 calle, Colonia Ciudad de Plata II.
2. Toma la ruta 801 con dirección a Parque Los Pinos, zona 7; pasa aproximadamente cada 10–20 min.
3. Viaja 4 paradas (7–10 min) y bájate en la parada #105: 33 avenida y 26 calle, Colonia Bethania.
4. Camina unos 160 m (2 min) hasta tu destino.

**Alternativa 2 — Ruta 801: #101 → #104** · 17–25 min · 555 m a pie

1. Camina unos 39 m (0–1 min) hasta la parada #101: Diagonal 24 y 14 calle, Colonia Ciudad de Plata II.
2. Toma la ruta 801 con dirección a Parque Los Pinos, zona 7; pasa aproximadamente cada 10–20 min.
3. Viaja 3 paradas (5–7 min) y bájate en la parada #104: Anillo Periférico y 30 avenida, Colonia 4 de febrero.
4. Camina unos 516 m (6–8 min) hasta tu destino.

**Alternativa 3 — Caminar** · 22–28 min · 1867 m a pie

1. Camina unos 1867 m (22–28 min).

## Q4. Trayecto corto en Colonia Bethania (#106 → #105)

_Propósito:_ Caminar debería ser mejor que tomar el bus

**Alternativa 1 — Caminar** · 6–8 min · 504 m a pie

1. Camina unos 504 m (6–8 min).

**Alternativa 2 — Ruta 801: #067 → #068** · 8–14 min · 151 m a pie

1. Camina unos 27 m (0 min) hasta la parada #067: 33 avenida y 31 calle, Colonia Bethania.
2. Toma la ruta 801 con dirección a Terminal 4a av. y 4a calle, zona 9; pasa aproximadamente cada 10–20 min.
3. Viaja 1 paradas (1–2 min) y bájate en la parada #068: 33 avenida y 26 calle, Colonia Bethania.
4. Camina unos 124 m (2 min) hasta tu destino.

**Alternativa 3 — Ruta 801: #067 → #069** · 10–16 min · 208 m a pie

1. Camina unos 27 m (0 min) hasta la parada #067: 33 avenida y 31 calle, Colonia Bethania.
2. Toma la ruta 801 con dirección a Terminal 4a av. y 4a calle, zona 9; pasa aproximadamente cada 10–20 min.
3. Viaja 2 paradas (2–3 min) y bájate en la parada #069: 33 avenida y 24 calle, Colonia Kjell Laugerud.
4. Camina unos 181 m (2–3 min) hasta tu destino.

**Evaluación:**

- La mejor opción es caminar.
- Paradas de abordaje o descenso con ubicación no verificada: #067; requieren validación en campo.

## Q5. Punto a 2 km al este de la terminal (#087) → Parque Los Pinos (#063)

_Propósito:_ Fuera de la cobertura de la ruta: no debería haber itinerario

Sin alternativas.

**Evaluación:**

- Sin itinerario: ninguna parada a una caminata razonable.
