# Plot Device Registration Stresstest results

source("plotter.R")

data <- loadResults("results.data.bz2")

pdf("requests.pdf", width=15, height=10, onefile=TRUE, family="Helvetica", pointsize=32)

mainTitle           <- "Device Registration Request Duration"
legendPos           <- c(1,1)

xSet <- data$RequestNumber
xTitle <- "Request Number"
ySet <- data$Duration
yTitle <- "Request Duration [s]"

xAxisTicks <- getIntegerTicks(xSet)   # Set to c() for automatic setting
yAxisTicks <- getIntegerTicks(ySet)   # Set to c() for automatic setting

f <- function(d) { return(unlist(strsplit(as.character(d), ':'))[[1]]) }

zSet <- unlist(lapply(as.vector(data$Error), f))
zTitle <- "Error{:epsilon:}"
zColorArray <- c("#00aa00", "red")

vSet   <- c()
vTitle <- ""
wSet   <- c()
wTitle <- ""

aSet   <- data$Release
aTitle <- "Release{:rho:}"
bSet   <- c()
bTitle <- ""

pSet   <- data$ParallelThreads
pTitle <- "Threads{:Theta:}"

plotstd6(mainTitle, pTitle, aTitle, bTitle, xTitle, yTitle, zTitle,
         pSet, aSet, bSet, xSet, ySet, zSet, zSortAscending=FALSE,
         vSet, wSet, vTitle, wTitle,
         xAxisTicks=xAxisTicks,yAxisTicks=yAxisTicks,
         zColorArray=zColorArray,
         type="l", legendPos=legendPos)

dev.off()
