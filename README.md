# Project webapp demos

* [FCGR-SEQ](https://baudrly.github.io/fcgrseq): easy conversion of variable-length DNA sequences into fixed-dimension images using [Frequency Chaos Game Representation](https://github.com/abhi1238/FCGR). The idea is to leverage powerful image processing techniques for genomic analysis and compute a diversity of 'image metrics' on the sequences as it turns out many characteristics of sequence functionality have a distinct fingerprint. It also enables novel alignment-free algorithmic approaches. The fixed size is also handy for computer vision and machine learning purposes.

* [Trivoroboost](https://baudrly.github.io/trivoroboost): an expansion of [serpentine binning](https://github.com/koszullab/serpentine) (a local, 2D and signal-aware binning of Hi-C contact maps), it performs the same approach using Delaunay graphs (and their counterpart, Voronoi diagrams). The pixels are grouped according to their values and their neighbors' in the graph, and the resulting set of binned regions is a Voronoi diagram. This lets the approach scale for very large contact maps and handle all representations in a sparse format.

* [CLOP](https://baudrly.github.io/clop): embedding sequence/annotation pairs in a vector space for visualization and classification purposes. Annotation here is understood in a relatively narrow (species, biotype) sense but can be easily extended conceptually. New, unknown sequences are matched to their nearest neighbors in that space for ultrafast semantic (or, in biological terms, functional) prediction.

Note that demos provide mock data to illustrate the interface and functionality but for actual analyses the user will need to supply their own models. The computations happen entirely on the browser - mind the size of your datasets.
