# Vendor Bill Templates (Odoo 17)

Módulo para crear y gestionar plantillas de facturas de proveedor recurrentes.

## Objetivo

Evitar la digitación repetitiva de facturas mensuales similares (mismo proveedor, concepto e importes), permitiendo generar nuevas facturas desde plantillas.

## Funcionalidades principales

- Gestión de plantillas de facturas de proveedor.
- Creación de plantilla desde una factura de proveedor existente.
- Generación individual o masiva de facturas desde plantillas seleccionadas.
- Generación manual con fecha indicada o fecha actual.
- Integración con `hr.contract` (contrato de empleado/colaborador).
- Opción de generación automática mediante `cron` (`Auto Generate`).
- Control para evitar duplicados por período.
- Soporte de secuencia de referencia para el número de documento.
- Inclusión de campos de cabecera relevantes (incluye `partner_bank_id` y `l10n_ec_sri_payment_id`).
- Traducciones `es_EC` para vistas, menús, acciones y campos.

## Dependencias

- `account`
- `hr_contract`
- `l10n_ec`

## Menús

- `Contabilidad > Proveedores > Plantillas de facturas de proveedor`
  - `Plantillas`
  - `Generar facturas`

## Flujo rápido

1. Crear plantilla manualmente o desde factura existente.
2. Ajustar líneas, diario, contrato y opciones de generación.
3. Generar factura desde formulario, lista (masivo) o wizard.
4. (Opcional) activar `Auto Generate` para generación automática.

## Seguridad

El acceso se gestiona por `security/ir.model.access.csv`.

## Licencia

Este módulo se distribuye bajo licencia **AGPL-3**. Ver archivo [LICENSE](./LICENSE).

## Autor

Openlab Ecuador
