# Plot Device Registration Stresstest results

source("plotter.R")

data <- loadResults("results.data.bz2")

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


table <- NULL
for(a in levels(factor(aSet))) {
for(p in levels(factor(pSet))) {

   dataSubset <- subset(data, (aSet == a) & (pSet == p))
   if(length(dataSubset$TotalRequests) > 0) {
      totalRequests <- mean(dataSubset$TotalRequests)
      totalTime     <- max(dataSubset$EndTime) - min(dataSubset$StartTime)
      successRate   <- length(subset(data, (aSet == a) & (pSet == p) & (zSet == "Success"))$TotalRequests) / totalRequests
      failureRate   <- length(subset(data, (aSet == a) & (pSet == p) & (zSet != "Success"))$TotalRequests) / totalRequests

      df <- data.frame(Release=a, ParallelThreads=p,
                       SuccessRate    = successRate,
                       FailureRate    = failureRate,
                       TotalRequests  = totalRequests,
                       TotalTime      = totalTime,
                       RequestsPerSec = totalRequests / totalTime,
                       MinDuration    = min(dataSubset$Duration),
                       MaxDuration    = max(dataSubset$Duration),
                       MeanDuration   = mean(dataSubset$Duration),
                       MedianDuration = median(dataSubset$Duration))
      table <- rbind(table, df)
   }

}}

write.csv(table, "throughput.csv")
print(table)
