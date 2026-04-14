# Raffle Management - Odoo 18 Community

Modulo personalizado para gestionar sorteos (rifas) mediante la venta de tickets numerados en la tienda virtual de Odoo 18 Community Edition.

## Requisitos

- Odoo 18 Community Edition
- Modulos dependientes: `sale_stock`, `website_sale`, `mail`, `portal`, `payment_custom`, `auth_signup`

## Instalacion

1. Copiar la carpeta `raffle_management` en el directorio de addons de Odoo
2. Reiniciar el servicio de Odoo
3. Activar el modo desarrollador
4. Ir a **Aplicaciones** > Actualizar lista de aplicaciones
5. Buscar "Sorteos" e instalar

## Configuracion

Despues de instalar, ir a **Ajustes > Sorteos** para configurar:

- **Responsable de Sorteos:** Usuario interno que recibe las actividades de cancelacion
- **Notificaciones por Email:** Activar/desactivar emails de ganador, cancelacion y resultados
- **WhatsApp API:** Credenciales para integracion futura (opcional)

## Funcionalidades Principales

- Creacion de sorteos con separacion automatica de inventario
- Cuadricula interactiva de tickets en la tienda virtual
- Reserva temporal de 5 minutos con countdown visual
- Portal del cliente con gestion de tickets y cancelacion
- Sorteo aleatorio auditable con semilla acumulativa
- Espera de 34 horas post-venta total antes de completar el sorteo
- 3 plantillas de email editables (ganador, cancelacion, resultados)
- Foto y link de redes sociales del ganador

## Estructura

```
raffle_management/
├── controllers/        # Tienda, registro, portal
├── models/             # Sorteo, ticket, herencias SO/partner/producto
├── views/              # Backend + templates frontend
├── wizard/             # Asistente de ejecucion del sorteo
├── static/             # JS (cuadricula, countdown) + SCSS
├── security/           # Grupos, permisos, record rules
├── data/               # Secuencias, crons, plantillas email
└── MANUAL_USUARIO_SORTEOS.md
```

## Documentacion

- `MANUAL_USUARIO_SORTEOS.md` — Manual de usuario con caso de uso paso a paso
- `ALCANCE_PROYECTO_SORTEOS.md` — Documento de alcance del proyecto

## Licencia

LGPL-3

## Autor

Walter Halm
