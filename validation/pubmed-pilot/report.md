# PubMed pilot result

The frozen sample contains 50 articles for which PubMed supplied received, accepted, and electronic-publication dates. This is a benchmark conditional on complete PubMed metadata, not a test of metadata coverage in ordinary journal populations.

## Sample and retrieval

| Publisher | Articles | Publisher pages retrieved |
|---|---:|---:|
| NAT | 20 | 0 |
| RSC | 10 | 0 |
| ACS | 10 | 0 |
| APS | 0 | 0 |
| ELS | 10 | 0 |
| **Overall** | **50** | **0** |

APS contributes no articles because the searched APS journals did not expose complete PubMed lifecycle triplets in the discovery records.

## Exact comparison

| Publisher | Date | N compared | Exact | Mismatch | Missing | Exact agreement |
|---|---|---:|---:|---:|---:|---:|
| OVERALL | received | 0 | 0 | 0 | 50 | not estimable |
| OVERALL | accepted | 0 | 0 | 0 | 50 | not estimable |
| OVERALL | published | 0 | 0 | 0 | 50 | not estimable |
| NAT | received | 0 | 0 | 0 | 20 | not estimable |
| NAT | accepted | 0 | 0 | 0 | 20 | not estimable |
| NAT | published | 0 | 0 | 0 | 20 | not estimable |
| RSC | received | 0 | 0 | 0 | 10 | not estimable |
| RSC | accepted | 0 | 0 | 0 | 10 | not estimable |
| RSC | published | 0 | 0 | 0 | 10 | not estimable |
| ACS | received | 0 | 0 | 0 | 10 | not estimable |
| ACS | accepted | 0 | 0 | 0 | 10 | not estimable |
| ACS | published | 0 | 0 | 0 | 10 | not estimable |
| APS | received | 0 | 0 | 0 | 0 | not estimable |
| APS | accepted | 0 | 0 | 0 | 0 | not estimable |
| APS | published | 0 | 0 | 0 | 0 | not estimable |
| ELS | received | 0 | 0 | 0 | 10 | not estimable |
| ELS | accepted | 0 | 0 | 0 | 10 | not estimable |
| ELS | published | 0 | 0 | 0 | 10 | not estimable |

## Conclusion

No publisher article page was retrieved successfully in this environment, so `appeer` produced no dates. Accuracy is therefore not estimable from this run. These unavailable outputs are counted as missing, not as date disagreements; `disagreements.csv` contains only genuine unequal date pairs.

Do not scale this exact procedure to 1,250 articles yet. First establish reliable publisher-page retrieval, then rerun this frozen pilot without changing the DOI list or parsers.
