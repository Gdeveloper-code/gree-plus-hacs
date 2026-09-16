# Gree Plus para Home Assistant

[English](README.md) | [Deutsch](README.de.md) | [Español](README.es.md) | [Français](README.fr.md) | [Português (Brasil)](README.pt-BR.md) | [日本語](README.ja.md) | [한국어](README.ko.md) | [简体中文](README.zh-Hans.md) | [繁體中文](README.zh-Hant.md)

Gree Plus es una integración no oficial de Home Assistant, mantenida por la comunidad y dirigida a entusiastas de la tecnología. Conecta a Home Assistant equipos de aire acondicionado GREE+ compatibles mediante la cuenta en la nube GREE+ del usuario.

## Funciones

- Control de encendido, modo HVAC, temperatura objetivo y velocidad del ventilador.
- Compatibilidad con Celsius, Fahrenheit y pasos de temperatura dependientes del modelo.
- Actualización del estado después de la configuración y de los comandos de control.
- Actualización manual sin sondeo continuo en segundo plano.

## Requisitos

- Home Assistant 2026.9.1 o posterior.
- Una cuenta GREE+ con al menos un equipo de aire acondicionado compatible.
- Acceso a Internet desde Home Assistant al servicio en la nube.

## Instalación

1. Abra HACS en Home Assistant.
2. Añada este repositorio como repositorio personalizado de la categoría **Integration**.
3. Descargue **Gree Plus** y reinicie Home Assistant.
4. Abra **Ajustes > Dispositivos y servicios > Añadir integración** y seleccione **Gree Plus**.

## Configuración

Seleccione la región de la cuenta e inicie sesión con la cuenta GREE+ asociada a los dispositivos. Home Assistant almacenará los datos de la sesión de autenticación para que la integración pueda volver a conectarse.

Si se solicita una verificación adicional, abra el enlace de inicio de sesión mostrado por Home Assistant, complete la verificación en el navegador y pegue la dirección completa `http://localhost/...` de la barra de direcciones. No envíe repetidamente el formulario de credenciales.

## Comportamiento de actualización

La integración no realiza sondeos continuos. Solicita el estado durante la configuración, después de los comandos de control y cuando se solicita una actualización manual de la entidad. Los cambios realizados fuera de Home Assistant pueden no aparecer hasta la siguiente actualización.

## Limitaciones

- Los controles compatibles se limitan al encendido, modo, temperatura objetivo y velocidad del ventilador.
- Los modos disponibles y los pasos de temperatura dependen de las capacidades del dispositivo.
- El funcionamiento depende de la disponibilidad y compatibilidad del servicio en la nube.

## Soporte y privacidad

Informe de los defectos mediante el gestor de incidencias del repositorio. Antes de adjuntar diagnósticos o registros, elimine identificadores de cuenta, datos de autenticación, identificadores de dispositivos, nombres e información de ubicación.

## Aviso legal

Este proyecto se desarrolla y se mantiene exclusivamente como una integración de Home Assistant. Los mantenedores no respaldan ni ofrecen soporte para su uso en productos o servicios comerciales no relacionados.

Este proyecto no está afiliado, respaldado ni soportado por Gree Electric Appliances, Inc. GREE y las marcas relacionadas pertenecen a sus respectivos propietarios. El servicio en la nube puede cambiar o dejar de estar disponible sin previo aviso. Use esta integración bajo su propia responsabilidad, revise las automatizaciones antes de activarlas y conserve un método oficial de control. Los mantenedores no se responsabilizan de interrupciones del servicio, funcionamiento involuntario de los dispositivos, pérdida de datos ni daños resultantes.

## Licencia

MIT
