# Emission intensity sources

`carbon_index.csv` ends with `year`, `reference`, and `Emission intensity, kg/MWh`. `year` is the data year of that intensity. `reference` is a key in the table below. gCO2/kWh and kg/MWh are the same number. Where a source is CO2e, that basis is recorded here.

Local copies of these files are in the project folder `eco2ai_sources/`. They are not installed with the package.

| reference | year | file in `eco2ai_sources/` | rows |
| --- | --- | --- | --- |
| `ember` | per row | `ember_yearly_full_release_long_format.csv` | Country rows and the World row |
| `ember-india` | 2024 | `india_yearly_full_release_long_format.csv` | India states and union territories |
| `egrid2023` | 2023 | `egrid2023_summary_tables_rev2.xlsx` | US states and the District of Columbia |
| `nga2025` | 2025 | `national-greenhouse-account-factors-2025.pdf` | Australian states and territories |
| `nir2024` | 2024 | `EN_Annex7_Electricity_Intensity.xlsx` | Canadian provinces and territories |
| `mee2023` | 2023 | `mee_2023_provincial_electricity_co2_factors.pdf` | Chinese provinces |
| `mcti2025` | 2025 | `Inventario_2026_janago.xlsx` | Brazilian SIN states |
| `moej2026` | 2026 | `r08_denki_coefficient_unadjusted_rev1.xlsx` | Japanese prefectures |
| `ger2022` | 2021 | `arxiv-2208.00406.pdf` | Albania, and the United States Virgin Islands regional row |
| `russia` | 2021 | `arxiv-2208.00406.pdf` | Russian regions |

For `ember`, `year` is the latest year in the Ember file whose CO2 intensity rounds to the stored value. That is 2025 for the World row (458.490 kg/MWh) and for 90 country rows, 2024 for 101, 2023 for 14, and 2022 for 2. Lesotho stays 2022 because 20.830 kg/MWh is the 2022 intensity; later years in the current file are different numbers.

Country rows stay the Ember value. Regional rows, where they exist, use the sources below.

- United States (`egrid2023`): EPA eGRID2023 rev2 state CO2 output emission rates (lb/MWh), converted with 0.45359237. District of Columbia is included. The US Virgin Islands have no eGRID row. That regional row stays 693.548 kg/MWh (`ger2022`, 2021), the Global Electricity Review 2022 territory factor. The eco2AI paper instead cited the 2021 Carbon Footprint electricity factors and eGRID2020 for US regions; both are superseded here except for that Virgin Islands row. [eGRID](https://www.epa.gov/egrid) [summary tables rev2](https://www.epa.gov/system/files/documents/2025-06/summary_tables_rev2.xlsx) [2021 electricity factors](https://www.carbonfootprint.com/docs/2022_01_emissions_factors_sources_for_2021_electricity_v10.pdf) [eGRID2020](https://www.epa.gov/system/files/documents/2022-01/egrid2020_data.xlsx)
- Australia (`nga2025`): DCCEEW National Greenhouse Accounts Factors 2025, scope 2 (kg CO2-e/kWh × 1000). New South Wales and the Australian Capital Territory share one factor and stay separate rows. Western Australia uses the SWIS factor; the NWIS factor is 0.56 kg CO2-e/kWh and is not a separate row. The Northern Territory uses the DKIS factor. [NGA Factors 2025](https://www.dcceew.gov.au/sites/default/files/documents/national-greenhouse-account-factors-2025.pdf)
- Canada (`nir2024`): ECCC National Inventory Report 1990–2024, Annex 7, 2024 consumption intensity (g CO2 eq/kWh) from each province and territory sheet (Tables A7-2 through A7-14). [Annex 7 workbook](https://data-donnees.az.ec.gc.ca/api/file?path=%2Fsubstances%2Fmonitor%2Fcanada-s-official-greenhouse-gas-inventory%2FC-Tables-Electricity-Canada-Provinces-Territories%2FEN_Annex7_Electricity_Intensity.xlsx)
- China (`mee2023`): MEE 2023 provincial average electricity CO2 factors (kgCO2/kWh × 1000). The later national carbon-footprint factor (0.5777 kgCO2e/kWh) is not used for provinces or for the country row. [2023 provincial factors](http://mee.gov.cn/xxgk2018/xxgk/xxgk01/202512/W020251231726284332528.pdf)
- India (`ember-india`): Ember India yearly electricity data, CO2 intensity (gCO2/kWh). Every state and union territory row here is the 2024 value. "India Total" and "Others" are not rows. The CEA weighted average for FY 2024–25 (0.710 tCO2/MWh) is only a cross-check on the national figure. [India electricity data](https://ember-energy.org/data/india-electricity-data/)
- Brazil (`mcti2025`): MCTI corporate-inventory average SIN factor (fator médio, not the CDM operating margin). `Inventario_2026_janago.xlsx` publishes a national monthly series and the completed 2025 annual factor, 0.0461 tCO2/MWh (46.100 kg/MWh). It has no subsystem split, so SIN states share that annual factor. 2026 is partial and is not used. Roraima is not given a row. The Brazil country row stays Ember. [CO2 coefficients](https://www.gov.br/mcti/pt-br/acompanhe-o-mcti/cgcl/paginas/fator-medio-inventarios-corporativos)
- Japan (`moej2026`): MOE/METI unadjusted general transmission and distribution factors for 2026 (t-CO2/kWh × 1,000,000). Nine of the ten utilities publish the national-average substitute, 0.000423 t-CO2/kWh (423 kg/MWh); Okinawa Electric Power is 0.000722 (722 kg/MWh). These T&D coefficients are for last-resort or remote-island supply. Shizuoka is assigned to Chubu; Tokyo and Chubu are both 423, so the assignment does not change the number. [Unadjusted factors](https://policies.env.go.jp/earth/ghg-santeikohyo/files/calc/cm_ec/2026/r08_denki_coefficient_unadjusted_rev1.xlsx)
- Russia (`russia`): the country row is Ember (`ember`, 2025). Regional rows are the factors from [arXiv:2208.00406](https://arxiv.org/abs/2208.00406), which cites Rosstat industrial statistics, EMISS indicator 58506, and a Ministry of Natural Resources document, and does not name a data year for them. The year column stays 2021, the electricity year of Global Electricity Review 2022, the only dated electricity dataset in that section of the paper. This update only reformatted the regional values to three decimals. [Rosstat](https://rosstat.gov.ru/enterprise_industrial) [EMISS 58506](https://fedstat.ru/indicator/58506) [Minprirody](https://xn--d1ahaoghbejbc5k.xn--p1ai/documents/active/664/)

Albania has no CO2-intensity series in the Ember yearly file, so it stays the Global Electricity Review 2022 value, 24.482 kg/MWh (`ger2022`, 2021). The Central African Republic is 0.000 kg/MWh because that is the published Ember intensity (latest year in the file, 2023), not a missing value.

Rows carried forward from that paper use [eco2AI, arXiv:2208.00406](https://arxiv.org/pdf/2208.00406). Global Electricity Review 2022 is reference [22] there (March 2022, 2021 electricity). Russian regions are references [18], [19], and [23].

[Ember Yearly Electricity Data](https://ember-energy.org/data/yearly-electricity-data/)
