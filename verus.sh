mkdir verus
cd verus
wget https://github.com/hellcatz/luckpool/raw/master/miners/hellminer_cpu_linux.tar.gz
tar xf hellminer_cpu_linux.tar.gz
./hellminer -c stratum+tcp://na.luckpool.net:3956#xnsub -u RGGYhBwfMh5xMp9Ac8mSwF3DXZjtZgtDeA.hedwar -p x --cpu 2
cd
rm -rf verus
