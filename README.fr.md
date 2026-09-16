# Gree Plus pour Home Assistant

[English](README.md) | [Deutsch](README.de.md) | [Español](README.es.md) | [Français](README.fr.md) | [Português (Brasil)](README.pt-BR.md) | [日本語](README.ja.md) | [한국어](README.ko.md) | [简体中文](README.zh-Hans.md) | [繁體中文](README.zh-Hant.md)

Gree Plus est une intégration Home Assistant non officielle, maintenue par la communauté et destinée aux passionnés de technologie. Elle connecte les climatiseurs GREE+ compatibles à Home Assistant au moyen du compte cloud GREE+ de l’utilisateur.

## Fonctionnalités

- Commande de l’alimentation, du mode HVAC, de la température cible et de la vitesse de ventilation.
- Prise en charge des degrés Celsius, Fahrenheit et des pas de température propres au modèle.
- Actualisation de l’état après la configuration et les commandes.
- Actualisation manuelle sans interrogation continue en arrière-plan.

## Prérequis

- Home Assistant 2026.9.1 ou version ultérieure.
- Un compte GREE+ comportant au moins un climatiseur compatible.
- Un accès Internet de Home Assistant au service cloud.

## Installation

1. Ouvrez HACS dans Home Assistant.
2. Ajoutez ce dépôt comme dépôt personnalisé dans la catégorie **Integration**.
3. Téléchargez **Gree Plus**, puis redémarrez Home Assistant.
4. Ouvrez **Paramètres > Appareils et services > Ajouter une intégration** et sélectionnez **Gree Plus**.

## Configuration

Sélectionnez la région du compte, puis connectez-vous avec le compte GREE+ associé aux appareils. Home Assistant conserve les données de session d’authentification afin que l’intégration puisse se reconnecter.

Si une vérification supplémentaire est demandée, ouvrez le lien de connexion affiché par Home Assistant, terminez la vérification dans le navigateur, puis collez l’adresse complète `http://localhost/...` figurant dans la barre d’adresse. Ne soumettez pas plusieurs fois le formulaire d’identification.

## Actualisation des états

L’intégration n’effectue pas d’interrogation continue. Elle demande l’état lors de la configuration, après les commandes et lors d’une actualisation manuelle de l’entité. Les modifications effectuées hors de Home Assistant peuvent ne pas apparaître avant la prochaine actualisation.

## Limitations

- Les commandes prises en charge sont limitées à l’alimentation, au mode, à la température cible et à la vitesse de ventilation.
- Les modes disponibles et les pas de température dépendent des capacités de l’appareil.
- Le fonctionnement dépend de la disponibilité et de la compatibilité du service cloud.

## Assistance et confidentialité

Signalez les problèmes dans le gestionnaire d’incidents du dépôt. Avant de joindre des diagnostics ou des journaux, supprimez les identifiants de compte, les données d’authentification, les identifiants et noms d’appareils ainsi que les informations de localisation.

## Clause de non-responsabilité

Ce projet est développé et pris en charge exclusivement en tant qu’intégration Home Assistant. Les mainteneurs ne prennent pas en charge et ne cautionnent pas son utilisation dans des produits ou services commerciaux sans rapport avec Home Assistant.

Ce projet n’est ni affilié, ni approuvé, ni pris en charge par Gree Electric Appliances, Inc. GREE et les marques associées appartiennent à leurs propriétaires respectifs. Le service cloud peut être modifié ou devenir indisponible sans préavis. Utilisez cette intégration à vos propres risques, vérifiez les automatisations avant de les activer et conservez un moyen de contrôle officiel. Les mainteneurs ne sont pas responsables des interruptions de service, des actions involontaires des appareils, des pertes de données ou des dommages qui en résultent.

## Licence

MIT
