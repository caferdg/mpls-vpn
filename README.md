# MPLS VPN configuration generator
Authors : Cafer DINGIL, Arthur-Mustapha FARWATI, Thomas FEUTREN, Baptiste GOUYEN, Margaux MASSOL

## About
School project made during the network architectures and services (NAS) class at INSA Lyon. The goal was to create a tool that generates the configuration of a MPLS VPN network from a JSON file and a GNS3 project.

## Execution
`python3 main.py <intentFile> <gnsProjectName>`
    - `intentFile` is the JSON file that describes the network's topology and the VPNs to create
    - `gnsProjectName` is the name of the GNS3 project which contains the adjacency datas of the network

## Rules
Rules for the intent file :
 - `lp-prefix` must have 24 bits (3 blocks of 8 bits)
 - For each autonomous system `ip-prefix` must have 24 bits (3 blocks of 8 bits)

## To do
 - Site sharing
 - avoid config wipe ...