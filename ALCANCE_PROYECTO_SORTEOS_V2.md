# DOCUMENTO DE ALCANCE DEL PROYECTO
## Sorteo Prime V2 — Odoo 18 Community

**Version del documento:** 1.0
**Fecha:** Mayo 2026
**Preparado por:** Equipo de Desarrollo Walter Halm
**Cliente:** Antonio Galli
**Plataforma:** Odoo 18 Community Edition
**Version actual del modulo:** 18.0.6.0.0
**Version objetivo:** 18.0.7.0.0

---

## 1. Resumen Ejecutivo

La version 2 del modulo Sorteo Prime incorpora tres bloques funcionales principales: (1) sistema de renuncia a la espera de 24 horas para acelerar la ejecucion del sorteo, (2) campos de redes sociales en el perfil del usuario con visibilidad publica, y (3) un sistema completo de notificaciones por email alineado a cada etapa del ciclo de vida del sorteo. Adicionalmente se incluye un paquete de seguridad para el servidor de produccion.

---

## 2. Requisitos Funcionales

### 2.1 Renuncia a la Espera de 24 Horas

**Objetivo:** Permitir que los usuarios aceleren la ejecucion del sorteo renunciando voluntariamente a su periodo de cancelacion de 24 horas.

**Funcionalidades:**

- Configuracion en el perfil del usuario con dos modos:
  - **Por ticket (default):** El usuario decide ticket por ticket si renuncia a la espera
  - **Global:** El usuario configura que todas sus compras futuras renuncien automaticamente
- La renuncia es **irreversible** una vez activada
- La renuncia solo se puede activar durante el periodo de espera (24h post-compra)
- Logica del sorteo:
  - Si TODOS los participantes renuncian → el sorteo se ejecuta inmediatamente
  - Si al menos uno NO renuncia → se espera hasta que se cumplan sus 24h naturales o el saldo de tiempo restante
  - La fecha del sorteo se recalcula dinamicamente segun el ultimo ticket pendiente de confirmacion
- **Countdown publico** visible en la pagina del sorteo mostrando el tiempo restante hasta la ejecucion
- Email de "compra firme" enviado al usuario cuando su ticket queda confirmado (por renuncia voluntaria o por cumplimiento natural de las 24h)

**Reglas de negocio:**
- El ultimo ticket vendido define la fecha maxima del sorteo (24h desde su compra)
- Si ese ultimo comprador renuncia, el siguiente ticket con mayor plazo pendiente define la nueva fecha
- El countdown se actualiza en tiempo real para todos los visitantes de la pagina del sorteo

---

### 2.2 Redes Sociales en Perfil de Usuario

**Objetivo:** Permitir que los participantes compartan sus redes sociales, visibles en la cuadricula de tickets y pagina de ganadores.

**Funcionalidades:**

- Cuatro campos opcionales en el perfil del usuario:
  - Instagram
  - Facebook
  - YouTube
  - TikTok
- Se almacena **solo el nombre de usuario** (sin @). El sistema construye el link completo automaticamente
- Editables desde el portal `/my/account`
- Visibilidad de las redes sociales del participante en:
  - (a) Perfil publico del usuario (accesible desde su avatar)
  - (b) Tooltip al pasar el cursor sobre un ticket vendido en la cuadricula
  - (c) Pagina de ganadores

**Nota:** El footer del sitio muestra las redes de Sorteo Prime (configuracion del sitio web), no las de los usuarios.

---

### 2.3 Sistema de Emails por Eventos

**Objetivo:** Implementar un flujo completo de notificaciones por email alineado a cada etapa del ciclo de vida del sorteo.

Todas las plantillas son editables desde el backend de Odoo (mail.template estandar).

#### Email 1: Compra — Detalles de pago

| Campo | Detalle |
|-------|---------|
| Disparador | Al crear la orden de venta (ticket reservado y agregado al carrito → confirmacion de compra) |
| Destinatario | Comprador |
| Contenido | Instrucciones de pago: cuenta bancaria, numero de Yape/Plin, imagen QR con monto |
| Configuracion | Imagen QR subida al sistema (ir.attachment) desde Ajustes > Sorteos. Numero de WhatsApp de contacto configurable. Mismos datos para todos los sorteos |

#### Email 2: Pago — Confirmacion

| Campo | Detalle |
|-------|---------|
| Disparador | Cuando el administrador confirma el pago (SO pasa de 'sent' a 'sale') |
| Destinatario | Comprador |
| Contenido | Confirmacion de que el pago fue registrado exitosamente. Detalle del ticket comprado |

#### Email 3: Compra Firme — Confirmacion definitiva

| Campo | Detalle |
|-------|---------|
| Disparador | Cuando el ticket queda firme: por cumplimiento natural de las 24h O por renuncia voluntaria del usuario |
| Destinatario | Comprador |
| Contenido | Confirmacion de compra firme + texto editable con recomendaciones y estrategias |
| Configuracion | El texto de recomendaciones es un campo HTML editable por sorteo desde el backend |

#### Email 4: Venta Total — Programacion del Sorteo

| Campo | Detalle |
|-------|---------|
| Disparador | Cuando se venden todos los tickets Y se confirma la fecha del sorteo |
| Destinatario | eventos@sorteoprime.com con **CC a todos los participantes** |
| Contenido | Invitacion al sorteo. Listado completo de: nicknames de participantes, numeros comprados por cada uno, fecha y hora programada del sorteo |
| Nota tecnica | Email preparado como disparador para N8N (buzón monitoreado). Se envia con CC visible (transparencia total entre participantes) |

#### Email 5: Resultado del Sorteo

| Campo | Detalle |
|-------|---------|
| Disparador | Despues de ejecutar el sorteo |
| Destinatario | eventos@sorteoprime.com con **CC a todos los participantes** |
| Contenido | Ganador (nickname + numero de ticket) + listado completo de participantes con sus numeros |
| Nota tecnica | Email preparado como disparador para N8N |

#### Email 6: Entrega del Premio

| Campo | Detalle |
|-------|---------|
| Disparador | Cuando el admin marca el sorteo como entregado |
| Destinatario | Depende del tipo de premio configurado en el sorteo |
| Contenido | Link a redes sociales con evidencia de entrega/pago |
| Configuracion | Campo en el sorteo: "Tipo de premio" → Fisico (email solo al ganador) / Dinero-Digital (email a todos los participantes) |

**Advertencia tecnica sobre emails con CC masivo:**
Los correos con CC a 100+ destinatarios pueden ser marcados como spam por algunos proveedores de correo. Se implementara tal como solicita el cliente (CC visible para transparencia), pero se recomienda monitorear la entregabilidad. Si se presentan problemas de deliverability, se puede migrar a envios individuales con listado de participantes incluido en el cuerpo.

---

### 2.4 Configuracion Adicional

- **Imagen QR de pago:** Subida desde Ajustes > Sorteos, visible en email de compra
- **Numero WhatsApp de contacto:** Configurable para incluir en instrucciones de pago
- **Texto de recomendaciones:** Campo HTML en cada sorteo, editable por el admin
- **Tipo de premio:** Seleccion en cada sorteo (Fisico / Dinero-Digital) que determina destinatarios del email de entrega
- **Modo de renuncia por defecto:** Configuracion en perfil de usuario (por ticket / global)

---

## 3. Seguridad del Servidor (Paquete Intermedio)

Implementacion de medidas de seguridad para el servidor de produccion:

| Medida | Descripcion |
|--------|-------------|
| Firewall (UFW) | Solo puertos 22, 80 y 443 abiertos. Todo lo demas bloqueado |
| Fail2ban | Bloqueo automatico de IPs con intentos fallidos de login (SSH + Odoo) |
| SSH Hardening | Cambio de puerto por defecto + deshabilitar login de root + acceso por usuario con sudo |
| Headers HTTP | HSTS, X-Content-Type-Options, X-XSS-Protection, Content-Security-Policy |
| Backup automatico | pg_dump diario con rotacion de 7 dias |
| Rate Limiting | Limites en Nginx para rutas sensibles: login, registro, reserva de tickets |
| SSL | Verificacion de renovacion automatica del certificado Let's Encrypt |

---

## 4. Correcciones V1 Incluidas (ya implementadas)

Como parte del soporte de la version 1, se realizaron las siguientes correcciones que se desplegaran junto con la V2:

| Correccion | Descripcion |
|------------|-------------|
| Registro duplicado | Mensaje claro cuando email o DNI ya existen ("Ya existe una cuenta...") en vez del error confuso de Odoo nativo |
| Campo "Sobre nombre" | Persiste al volver con error + autocomplete=off para evitar cache del navegador |
| Flujo de compra | Click en ticket redirige al carrito (/shop/cart) con countdown de 5 min, no directo a checkout |
| Boton duplicado | Eliminado "Continuar comprando" duplicado en pagina de pago |
| Reset de contrasena | Corregido: el flujo de recuperar contrasena ya no pide WhatsApp ni DNI, funciona 100% nativo |
| Rendimiento servidor | Desactivados crons innecesarios en DBs secundarias (calidad, backup) |

---

## 5. Certificacion de Seguridad del Modulo

El cliente solicito la verificacion de 10 puntos de seguridad sobre el modulo desarrollado. Se certifica el cumplimiento de todos:

| # | Punto | Estado | Comentario |
|---|-------|--------|------------|
| 1 | Inyeccion SQL | ✅ Cumple | 100% ORM de Odoo. Sin consultas SQL crudas en todo el codigo |
| 2 | Anti-DoS/DDoS | ✅ Cumple | Tickets limitados por stock. Reserva con timeout 5 min. Endpoints con autenticacion. Rate limiting en Nginx (V2) |
| 3 | Gestion de puertos | ✅ Cumple | Solo 80/443 expuestos (Nginx). Odoo 8069/8072 internos al Docker. Sin llamadas a APIs externas |
| 4 | Usuarios privilegiados | ✅ Cumple | Sin usuarios ocultos. Permisos via grupos estandar (ir.model.access + res.groups) |
| 5 | Puertas traseras | ✅ Cumple | Codigo sin ofuscacion. Sin claves hardcodeadas, rutas secretas ni funciones sin autenticacion |
| 6 | Copias de seguridad | ✅ Cumple | Todo en PostgreSQL. Archivos en campos Binary (DB). Compatible con pg_dump y backup nativo. Backup automatico diario (V2) |
| 7 | Seguridad de red | ✅ Cumple | Sin llamadas externas activas. Endpoints publicos solo lectura. Acciones requieren autenticacion |
| 8 | Seguridad de aplicaciones | ✅ Cumple | Herencias con xpath estandar. sudo() documentado y justificado. Record rules para todos los niveles |
| 9 | Seguridad fisica | ✅ Cumple | Sin acceso a filesystem. Sin archivos en rutas publicas no controladas |
| 10 | Logs y auditoria | ✅ Cumple | mail.thread registra: creacion sorteos, cambios estado, ventas, cancelaciones, ganador, entregas |

---

## 6. Exclusiones (No incluido en V2)

Para evitar ambiguedades, se detallan las funcionalidades que **NO** forman parte de este alcance:

| Exclusion | Motivo |
|-----------|--------|
| Automatizacion de pagos | Se mantiene confirmacion manual por el admin. El cliente desarrolla su propia solucion con n8n de forma independiente |
| Desarrollo de flujos N8N | Los emails a eventos@sorteoprime.com funcionan como disparador. La configuracion y desarrollo de los flujos dentro de n8n es responsabilidad del cliente |
| Integracion WhatsApp (Twilio/Meta) | La estructura esta preparada en el modulo (modelo whatsapp.message, credenciales en ajustes) pero la activacion y conexion con un proveedor no esta incluida |
| Integracion Mercado Pago | Disponible nativamente en Odoo 18 pero su configuracion y activacion no forma parte de este alcance |
| Integracion ApiPeru.dev | Autocompletado de datos por DNI. Requiere cuenta activa en apiperu.dev. No incluido |
| Facturacion electronica (SUNAT) | Requiere Odoo Enterprise (l10n_pe_edi) o PSE externo (Nubefact). No disponible en Community |
| Mantenimiento DB "calidad" | El entorno calidad.sorteoprime.com no forma parte del alcance de desarrollo ni soporte |
| Migracion a otro servidor/hosting | El despliegue se realiza en el VPS Contabo actual (158.220.103.134) |
| Diseno grafico | Imagenes QR, banners o material visual deben ser provistos por el cliente |
| Contenido de emails | El texto especifico de "recomendaciones y estrategias" y demas contenidos de las plantillas los redacta el cliente. El desarrollo provee la estructura y campos editables |

---

## 7. Cronograma Estimado

| Bloque | Descripcion | Horas estimadas |
|--------|-------------|-----------------|
| 2.1 | Renuncia a espera 24h + countdown publico | 8-10h |
| 2.2 | Redes sociales en perfil + tooltip cuadricula + perfil publico | 5-6h |
| 2.3 | Sistema de 6 emails por eventos | 14-18h |
| 2.4 | Configuracion adicional (QR, tipo premio, texto recomendaciones) | 3-4h |
| 3 | Seguridad del servidor (Paquete Intermedio) | 12-14h |
| — | Testing integral + despliegue | 4-5h |
| **Total** | | **46-57 horas** |

**Plazo de entrega estimado:** 8-10 dias habiles desde la aprobacion.

---

## 8. Inversion

| Concepto | Horas | Monto (USD) |
|----------|-------|-------------|
| Desarrollo funcional (bloques 2.1 a 2.4) | 30-38h | $XXX |
| Seguridad del servidor (bloque 3) | 12-14h | $XXX |
| Testing + despliegue | 4-5h | $XXX |
| **Total** | **46-57h** | **$XXX** |

*Nota: Completar con tarifa hora acordada entre las partes.*

---

## 9. Condiciones

### Forma de pago
- **50% al aprobar** el presente documento e iniciar el desarrollo
- **50% al entregar** la version final desplegada en produccion

### Periodo de validacion
- El cliente dispone de **1 semana (7 dias calendario)** posterior a la entrega para validar el funcionamiento de las nuevas funcionalidades
- Durante este periodo se corrigen bugs o desviaciones respecto a lo descrito en este documento sin costo adicional
- Requerimientos nuevos o cambios de alcance posteriores a la aprobacion de este documento se cotizan por separado

### Soporte post-entrega
- Soporte incluido durante el periodo de validacion (7 dias)
- Soporte posterior al periodo de validacion se cotiza por separado

### Entregables
- Codigo fuente actualizado (version 18.0.7.0.0)
- Modulo desplegado en produccion (sorteoprime.com)
- Servidor con medidas de seguridad implementadas
- Documentacion actualizada

---

## 10. Supuestos y Riesgos Tecnicos

### Supuestos
- El cliente provee acceso SSH al servidor de produccion (158.220.103.134) durante todo el desarrollo
- El cliente provee las imagenes QR y contenido textual de las plantillas de email
- El servidor de correo saliente esta configurado y operativo en Odoo
- El dominio sorteoprime.com permanece activo y apuntando al VPS actual
- El entorno de produccion no sera modificado por terceros durante el desarrollo

### Riesgos tecnicos

| Riesgo | Impacto | Mitigacion |
|--------|---------|------------|
| Emails con CC a 100+ destinatarios marcados como spam | Participantes no reciben correos | Monitorear entregabilidad. Si falla, migrar a envios individuales (costo adicional de ~2h) |
| Proveedor de email limita envios masivos | Emails no se envian | Verificar limites del SMTP configurado. Considerar servicio dedicado (SendGrid, Mailgun) |
| Cliente modifica templates o configuracion en produccion durante desarrollo | Conflictos al desplegar | Coordinar ventanas de despliegue. No editar templates durante periodo de desarrollo |
| Cambios en la API de Odoo en actualizaciones futuras | Funcionalidades dejan de operar | El modulo se desarrolla para Odoo 18.0. Actualizaciones mayores pueden requerir adaptacion |

---

## 11. Aprobacion

| | Cliente | Desarrollador |
|---|---|---|
| Nombre | Antonio Galli | Walter Halm |
| Fecha | | |
| Firma | | |

---

*Documento preparado por el equipo de desarrollo.*
*Sorteo Prime V2 — Version del modulo objetivo: 18.0.7.0.0*
