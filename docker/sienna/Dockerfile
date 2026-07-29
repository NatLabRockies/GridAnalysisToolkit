# Builds a Sienna environment that generates RTS-GMLC fixture data for GAT.
#
#   docker build --build-arg SIENNA_VERSION=4 -t gat-sienna:v4 .
#   docker build --build-arg SIENNA_VERSION=5 -t gat-sienna:v5 .
#
# Then run with a host volume mounted at /output to capture sys.json +
# simulation_store.h5:
#
#   docker run --rm -v "$(pwd)/example_data/sienna/v4:/output" gat-sienna:v4

ARG JULIA_VERSION=1.11
FROM julia:${JULIA_VERSION}-bookworm

ARG SIENNA_VERSION=4
ENV SIENNA_VERSION=${SIENNA_VERSION}

RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates git \
    && rm -rf /var/lib/apt/lists/*

# libgit2's bundled CA store breaks under colima/corporate-MITM environments;
# CLI git uses the OS cert store which works.
ENV JULIA_PKG_USE_CLI_GIT=true

WORKDIR /work

COPY Project.toml ./
COPY Manifest.v${SIENNA_VERSION}.toml ./Manifest.toml

RUN julia --project=. -e 'using Pkg; Pkg.instantiate(); Pkg.precompile()'

COPY generate.jl ./

VOLUME ["/output"]
CMD ["julia", "--project=.", "generate.jl", "/output"]
