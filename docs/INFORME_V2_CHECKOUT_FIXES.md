# Informe de Desarrollo v2 — Correcciones de Flujo de Compra y Registro

**Fecha:** Julio 2025  
**Versión:** 18.0.7.0.0 (rama develop/v2-checkout-fixes)  
**Solicitado por:** Antonio Galli  
**Desarrollado por:** Walter Halm  

---

## 1. Resumen de Cambios Implementados

| N° | Requerimiento | Estado |
|----|--------------|--------|
| 1 | Eliminar columna de cantidad en el carrito para tickets de rifa | ✅ Implementado |
| 2 | Checkout directo al pago sin pasos intermedios | ✅ Implementado |
| 3 | Quitar campo "Nombre" del registro (se auto-genera con nickname o DNI) | ✅ Implementado |
| 4a | Quitar "Nombre de la empresa" del formulario de dirección | ✅ Implementado |
| 4b | Predefinir tipo de identificación = DNI | ✅ Implementado |
| 4c | Eliminar paso de dirección del checkout de rifas | ✅ Implementado |

---

## 2. Detalle Técnico por Punto

### 2.1 Carrito sin columna de cantidad

Se oculta el selector de cantidad (+/-) exclusivamente para líneas que contienen tickets de rifa. Los productos normales de la tienda siguen mostrando la cantidad de forma habitual.

Cada ticket sigue siendo una fila independiente con cantidad fija = 1, tal como estaba diseñado en la v1.

---

### 2.2 Checkout directo al pago

**¿Por qué no se redirige automáticamente al pago al seleccionar un ticket?**

En la vida real, un usuario puede querer seleccionar varios números antes de pagar. Si lo redirigimos al pago después de cada selección, tendría que volver a la cuadrícula, elegir otro número, volver al pago, y así sucesivamente. Esto genera una experiencia frustrante.

**Solución implementada:** Se desarrolló un banner informativo (sticky) que aparece encima de la cuadrícula de números al seleccionar el primer ticket. Este banner:

- Muestra los números específicos seleccionados (ej: "2 tickets seleccionados: N° 5, N° 12")
- Indica el tiempo límite de 5 minutos
- Incluye un botón "Proceder al pago" que lleva directamente a la pantalla de pago
- Se actualiza dinámicamente al agregar o quitar tickets
- Desaparece si se quitan todos los tickets o si expiran

Este patrón es el mismo que utilizan plataformas como Ticketmaster, StubHub y MercadoLibre para la selección de asientos/tickets con reserva temporal.

**Flujo resultante para el usuario:**
1. Selecciona uno o más números en la cuadrícula
2. Aparece el banner con sus números y el botón de pago
3. Click en "Proceder al pago" → pantalla de pago directamente (sin carrito, sin dirección)

---

### 2.3 Registro sin campo "Nombre"

El campo "Nombre" se oculta del formulario de registro. El sistema genera automáticamente el nombre del contacto usando:
- El **nickname** si el usuario lo ingresó
- El **número de DNI** si no ingresó nickname

Cuando se integre la API de RENIEC en el futuro, el nombre temporal será reemplazado automáticamente por el nombre real obtenido del documento de identidad.

---

### 2.4 Dirección: sin empresa, DNI fijo, sin paso de dirección

- **"Nombre de la empresa"** se oculta del formulario de dirección globalmente (confirmado que no se vende a empresas).
- **Tipo de identificación** se asigna automáticamente como DNI al registrarse (si el módulo de localización peruana está instalado).
- **País** se asigna automáticamente como Perú.
- **Teléfono** se asigna automáticamente con el número de WhatsApp ingresado.
- **El paso de dirección no se muestra** durante la compra de tickets. La dirección completa solo se solicitará cuando un usuario resulte ganador y se deba coordinar la entrega del premio.

---

## 3. Mejoras Adicionales de UX (no solicitadas pero necesarias)

### 3.1 Distinción visual de tickets propios vs. ajenos

Cuando varios usuarios están seleccionando tickets simultáneamente, todos ven los tickets reservados en color naranja. Para evitar confusión, se implementó:

- **Tickets propios (en mi carrito):** Naranja con borde grueso oscuro + cursor pointer (clickeable para quitar)
- **Tickets de otros usuarios:** Naranja con borde fino + cursor default (no clickeable)

### 3.2 Deseleccionar tickets

El usuario puede hacer click en un ticket propio (naranja con borde grueso) para quitarlo del carrito. Aparece un popup de confirmación "¿Quitar del carrito?" antes de ejecutar la acción.

### 3.3 Expiración inteligente en el carrito

Si el usuario navega al carrito (/shop/cart) y un ticket expira:
- Se muestra "Expirado" en la línea correspondiente
- Se elimina automáticamente del carrito vía AJAX
- Si tenía múltiples tickets, solo se elimina el expirado (los demás siguen activos)
- Solo se redirige a la tienda cuando TODOS los tickets expiraron

### 3.4 Ícono del portal

Se reemplazó el ícono del módulo (PNG grande) por un SVG de 64x64 diseñado para el portal, siguiendo el mismo estilo visual que los demás módulos de Odoo (Ventas, Compras, etc.).

---

## 4. Guía de Testing para Validación

### Test 1: Registro de nuevo usuario

1. Abrir ventana de incógnito → ir a `/web/signup`
2. **Verificar:** No aparece campo "Nombre", no aparece campo "Contraseña"
3. Llenar: Email, WhatsApp (+51 999111222), DNI (87654321), Nickname (TestUser)
4. Click "Registrarse"
5. **Verificar en backend (Contactos):**
   - Nombre = TestUser
   - País = Perú
   - Teléfono = +51 999111222
   - Tipo de identificación = DNI

### Test 2: Selección de múltiples tickets

1. Loguearse → ir a un sorteo activo en la tienda
2. Click en un ticket verde → popup "Reservar" → confirmar
3. **Verificar:** Aparece banner "1 ticket seleccionado: N° X — Tenés 5 minutos..."
4. Click en otro ticket verde → confirmar
5. **Verificar:** Banner actualiza a "2 tickets seleccionados: N° X, N° Y"
6. **Verificar:** Los tickets propios tienen borde naranja grueso

### Test 3: Deseleccionar un ticket

1. Click en un ticket propio (naranja con borde grueso)
2. Aparece popup "¿Quitar del carrito?"
3. Confirmar "Quitar"
4. **Verificar:** Ticket vuelve a verde, banner actualiza el conteo

### Test 4: Checkout directo

1. Con tickets seleccionados, click en "Proceder al pago" del banner
2. **Verificar:** Se llega directamente a la pantalla de pago (Yape/Plin/Tuky)
3. **Verificar:** No se pasó por el carrito ni por el formulario de dirección

### Test 5: Carrito (acceso manual)

1. Ir manualmente a `/shop/cart`
2. **Verificar:** Los tickets aparecen sin selector de cantidad (+/-)
3. **Verificar:** Aparece countdown de reserva en cada línea

### Test 6: Formulario de dirección (acceso manual)

1. Ir manualmente a `/shop/address`
2. **Verificar:** No aparece "Nombre de la empresa"

### Test 7: Productos normales (si aplica)

1. Agregar un producto normal (no-rifa) al carrito
2. Proceder al checkout
3. **Verificar:** SÍ pide dirección completa (calle, ciudad, etc.)
4. **Verificar:** SÍ muestra selector de cantidad en el carrito

### Test 8: Expiración de reserva

1. Seleccionar un ticket y NO pagar
2. Esperar 5 minutos
3. **Verificar en la cuadrícula:** El ticket vuelve a verde, banner desaparece
4. **Verificar en el carrito (si estaba ahí):** La línea se elimina automáticamente

### Test 9: Usuario no registrado (flujo completo)

1. Abrir ventana de incógnito (sin sesión)
2. Ir a la tienda → entrar a un sorteo activo
3. Seleccionar un ticket verde → popup "Reservar" → confirmar
4. **Verificar:** Aparece banner con el número seleccionado
5. Click en "Proceder al pago"
6. **Verificar:** Aparece modal informativo:
   - Título: "Para completar tu compra"
   - Texto: "Necesitás iniciar sesión o crear una cuenta para proceder al pago"
   - Botones: "Iniciar sesión" y "Crear cuenta"
   - Link: "Seguir eligiendo números" (cierra el modal)
7. Click en "Crear cuenta" → formulario de registro
8. Completar registro (WhatsApp + DNI + Nickname)
9. **Verificar:** Después del registro, redirige directamente a la pantalla de pago
10. **Verificar:** Los tickets reservados siguen en el carrito (si no pasaron los 5 min)

### Test 10: Concurrencia (dos usuarios simultáneos)

1. Abrir dos navegadores diferentes (o uno normal + uno incógnito), ambos logueados con usuarios distintos
2. Ambos ven la misma cuadrícula del sorteo
3. **Usuario A** reserva ticket #5 → se pone naranja con borde grueso (propio)
4. **Usuario B** espera 30 segundos (refresco automático) → ve ticket #5 naranja con borde fino (ajeno)
5. **Usuario B** intenta hacer click en #5 → no pasa nada (no es clickeable)
6. **Usuario B** reserva ticket #12 → se pone naranja con borde grueso (propio)
7. **Verificar:** Cada usuario ve sus propios tickets con borde grueso y los ajenos con borde fino

---

## 5. Decisiones Técnicas y Justificación

### ¿Por qué un banner y no un redirect automático?

Odoo nativamente maneja el flujo de compra desde el carrito (/shop/cart → /shop/checkout → /shop/payment). Modificar este flujo con redirects automáticos puede generar conflictos con:
- El manejo de sesiones de Odoo
- Los métodos de pago que esperan cierto estado del pedido
- Futuras actualizaciones del módulo website_sale

El banner es una solución **no invasiva** que respeta el flujo nativo pero ofrece un atajo directo al usuario. Si el usuario prefiere ir al carrito manualmente, puede hacerlo sin problemas.

### ¿Por qué reducir campos obligatorios en vez de eliminar el paso?

Eliminar completamente el paso de dirección del checkout requeriría sobreescribir controllers nativos de Odoo, lo cual:
- Rompe con actualizaciones futuras de Odoo
- Puede generar errores en módulos que dependen de ese flujo (payment_custom, delivery, etc.)
- Es difícil de mantener

En cambio, reducir los campos obligatorios a solo `name` (que siempre existe) hace que la validación nativa pase automáticamente y el sistema salte el paso sin necesidad de modificar el flujo base.

### ¿Por qué no se modificó el formulario de dirección con condiciones dinámicas?

Agregar condiciones tipo "si es rifa, ocultar estos campos" directamente en el template de dirección de Odoo (`website_sale.address`) implicaría:
- Heredar un template muy complejo con muchas dependencias
- Riesgo de romper el formulario para productos normales
- Conflictos con otros módulos que también heredan ese template

La solución elegida (reducir campos obligatorios + datos auto-completados al registrarse) logra el mismo resultado sin tocar el formulario.

### ¿Por qué un modal de login en vez de redirigir directamente?

Cuando un visitante no registrado selecciona tickets y hace click en "Proceder al pago", el sistema nativo de Odoo lo redirige a `/web/login` sin explicación. Esto genera confusión porque:
- El usuario no entiende por qué lo sacaron de la página
- Pierde el contexto visual de lo que estaba haciendo
- Si tarda en registrarse, su reserva de 5 minutos puede expirar

El modal informativo resuelve esto:
- Explica claramente POR QUÉ necesita registrarse
- Ofrece dos opciones claras (login o registro)
- Permite volver a la cuadrícula si quiere seguir eligiendo
- Después del registro/login, redirige directamente al pago

### ¿Por qué se permite reservar sin estar logueado?

El endpoint `/shop/raffle/add_ticket` acepta usuarios públicos (`auth='public'`) porque:
- Permite que el visitante explore y seleccione números antes de comprometerse a registrarse
- Reduce la fricción inicial (no pide registro para "mirar")
- El registro se pide recién al momento de pagar, cuando el usuario ya tomó la decisión de compra
- Es el mismo patrón que usan Amazon, MercadoLibre y Ticketmaster

---

## 6. Consideraciones Importantes

### Campos nativos de Odoo

Es importante mencionar que **no es recomendable eliminar o modificar campos nativos de Odoo** (como `name` en `res.partner`, `street` en direcciones, etc.) ya que:

1. **Otros módulos dependen de ellos:** Facturación, envíos, reportes, contabilidad — todos esperan que estos campos existan y tengan datos.
2. **Actualizaciones de Odoo:** Cada nueva versión puede agregar validaciones sobre campos existentes. Si los eliminamos, la actualización puede fallar.
3. **Integraciones futuras:** Si en el futuro se integra facturación electrónica (SUNAT/RENIEC), se necesitarán todos los datos del contacto.

Por esta razón, la estrategia fue **ocultar visualmente** los campos que no aplican al negocio de rifas, pero mantenerlos funcionales internamente. Los datos se completan automáticamente con valores mínimos (País=Perú, Teléfono=WhatsApp) para que el sistema funcione correctamente sin exponer formularios innecesarios al usuario final.

### Datos que se completarán en el futuro

| Dato | Cuándo se completa | Cómo |
|------|-------------------|------|
| Nombre real | Al integrar API RENIEC | Automático por DNI |
| Dirección completa | Al ganar un premio | Formulario en portal del ganador |
| Tipo de identificación | Al registrarse | Automático (DNI) |

---

## 7. Archivos Modificados

```
controllers/main.py              → Checkout sin dirección + endpoints remove_ticket + my_ticket_ids
controllers/auth.py              → Auto-generar nombre con nickname/DNI
models/res_users.py              → Asignar País, DNI, Teléfono al registrarse
static/src/js/raffle_ticket_grid.js   → Banner con números, deseleccionar, distinción propios/ajenos,
                                        modal login para usuarios no registrados
static/src/js/raffle_cart_countdown.js → Expiración independiente por línea
static/src/scss/raffle_ticket_grid.scss → Estilos tickets propios vs ajenos + modal login
views/templates/auth_signup.xml  → Ocultar nombre + quitar required
views/templates/raffle_cart.xml  → Ocultar cantidad para tickets
views/templates/raffle_checkout.xml → Ocultar empresa (NUEVO)
views/templates/raffle_ticket_grid.xml → data-is-public para detectar usuario no registrado
views/templates/raffle_portal.xml → Ícono SVG del portal
static/src/img/ticket.svg        → Ícono SVG para portal (NUEVO)
docs/INFORME_V2_CHECKOUT_FIXES.md → Este documento (NUEVO)
__manifest__.py                  → Agregar nuevo template
```

---

## 8. Próximos Pasos

1. **Validación por parte del cliente** de los puntos implementados
2. **Revertir cambios de prueba** (botón "Ejecutar Sorteo" temporal) antes del deploy
3. **Merge a main** una vez validado
4. **Deploy a producción** (sorteoprime.com)

---

Quedamos a disposición para cualquier consulta o ajuste adicional.

**Walter Halm**  
Desarrollo Odoo 18
